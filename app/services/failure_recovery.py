from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Run, Task, TaskStatus
from app.services.audit import record

RECOVERY_MARKER = "[DEVPILOT_FAILURE_RECOVERY_V1]"
_ORIGIN_RE = re.compile(r"\[failure-origin-task:([^\]]+)\]", re.IGNORECASE)


def is_failure_recovery_task(task: Task | None) -> bool:
    return bool(task and (task.source == "failure-recovery" or RECOVERY_MARKER in str(task.prompt or "")))


def recovery_origin_task_id(task: Task | None) -> str:
    if not task:
        return ""
    match = _ORIGIN_RE.search(str(task.prompt or ""))
    return match.group(1).strip() if match else ""


def latest_run_for_task(db: Session, task_id: str) -> Run | None:
    return db.scalar(
        select(Run)
        .where(Run.task_id == task_id)
        .order_by(Run.started_at.desc(), Run.attempt.desc())
        .limit(1)
    )


def find_failure_recovery_task(db: Session, original_task: Task) -> Task | None:
    marker = f"[failure-origin-task:{original_task.id}]"
    return db.scalar(
        select(Task)
        .where(
            Task.workspace_id == original_task.workspace_id,
            Task.project_id == original_task.project_id,
            Task.source == "failure-recovery",
            Task.prompt.contains(marker),
        )
        .order_by(Task.created_at.desc())
        .limit(1)
    )


def _safe_original_prompt(task: Task, limit: int = 20_000) -> str:
    text = str(task.prompt or "").strip()
    return text if len(text) <= limit else f"{text[:limit].rstrip()}\n\n[conteúdo original truncado pelo fluxo de recuperação]"


def _run_payload(run: Run | None) -> dict:
    if not run or not run.logs:
        return {}
    try:
        value = json.loads(run.logs)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _detected_cause(payload: dict) -> str:
    context = payload.get("failure_context") if isinstance(payload, dict) else None
    if isinstance(context, dict):
        cause = str(context.get("cause") or "").strip()
        if cause:
            return cause[:2400]

    healing = payload.get("self_healing") if isinstance(payload, dict) else None
    steps = healing.get("steps") if isinstance(healing, dict) else None
    if isinstance(steps, list):
        for step in reversed(steps):
            if not isinstance(step, dict) or str(step.get("state") or "") != "detected":
                continue
            cause = str(step.get("message") or "").strip()
            if cause:
                return cause[:2400]

    raw = str(payload.get("stderr") or "").strip() if isinstance(payload, dict) else ""
    return raw[:2400]


def _recommended_action(category: str, cause: str, requires_authorization: bool) -> str:
    if category == "github_auth":
        return "Revalidar a credencial GitHub vinculada ao projeto, confirmar acesso ao repositório e repetir esta mesma etapa."
    if category == "codex_auth":
        return "Autenticar o Codex no worker e repetir esta mesma etapa sem alterar o objetivo da rodada."
    if category == "git_network":
        return "Restabelecer a conectividade com o repositório e repetir esta mesma etapa."
    if category == "repository_state":
        return "Reparar ou recriar com segurança o checkout local e repetir esta mesma etapa."
    if category == "filesystem_permission":
        return "Corrigir somente a permissão necessária no ambiente de execução e repetir esta mesma etapa."
    if category == "database":
        return "Restabelecer o banco do DevPilot, validar a integridade e repetir esta mesma etapa."
    if requires_authorization:
        return "Resolver somente a autorização indicada pelo diagnóstico e repetir esta mesma etapa."
    if cause:
        return f"Corrigir a causa técnica registrada ({cause[:700]}) e repetir exatamente esta etapa."
    return "Corrigir a causa técnica registrada e repetir exatamente esta etapa."


def enrich_failure_from_run(run: Run | None, failure: dict | None) -> dict:
    result = dict(failure or {})
    payload = _run_payload(run)
    cause = _detected_cause(payload)
    context = payload.get("failure_context") if isinstance(payload, dict) else None

    category = str(result.get("category") or "unknown")
    if category == "unknown" and isinstance(context, dict):
        contextual_category = str(context.get("category") or "").strip()
        if contextual_category:
            category = contextual_category

    requires_authorization = bool(result.get("requires_authorization", False))
    generic_message = str(result.get("message") or "").strip()
    technical_message = cause or str(result.get("technical_message") or "").strip() or generic_message
    message = generic_message
    if category == "unknown" and technical_message:
        message = technical_message
    if not message:
        message = technical_message or "Falha sem mensagem detalhada."

    result.update({
        "category": category or "unknown",
        "code": str(result.get("code") or "EXECUTION_FAILED"),
        "message": message[:2400],
        "technical_message": technical_message[:2400],
        "requires_authorization": requires_authorization,
        "recommended_action": _recommended_action(category, technical_message, requires_authorization)[:2400],
    })
    return result


def recovery_prompt(original_task: Task, run: Run | None, failure: dict) -> str:
    failure = enrich_failure_from_run(run, failure)
    category = str(failure.get("category") or "unknown")
    code = str(failure.get("code") or "EXECUTION_FAILED")
    message = str(failure.get("message") or "Falha sem mensagem detalhada.")
    technical_message = str(failure.get("technical_message") or message)
    recommended_action = str(
        failure.get("recommended_action")
        or "Corrigir a causa técnica registrada e repetir exatamente esta etapa."
    )
    authorization = bool(failure.get("requires_authorization"))
    run_id = run.id if run else ""
    return (
        f"{RECOVERY_MARKER}\n[DEVPILOT_MODE=fix]\n[failure-origin-task:{original_task.id}]\n"
        f"[failure-origin-run:{run_id}]\n[failure-category:{category}]\n[failure-code:{code}]\n"
        f"[failure-requires-authorization:{str(authorization).lower()}]\n\n"
        "MISSÃO DE RECUPERAÇÃO\nUma execução anterior falhou depois do ciclo normal de autocorreção. Sua função é remover a causa raiz de forma verificável, sem repetir cegamente a mesma tentativa.\n\n"
        "PROTOCOLO OBRIGATÓRIO\n"
        "1. Leia AGENTS.md, documentação aplicável e o estado real do repositório antes de alterar qualquer coisa.\n"
        "2. Use a falha abaixo como evidência inicial, mas confirme a causa raiz no ambiente atual.\n"
        "3. Preserve código estável, dados e credenciais. Não force permissões, não apague dados e não contorne autorizações.\n"
        "4. Se a causa depender de credencial, autenticação, permissão ou decisão humana ainda ausente, NÃO improvise. Pare e descreva exatamente a intervenção necessária.\n"
        "5. Execute especificamente a CORREÇÃO PROPOSTA abaixo; se a evidência real mostrar outra causa, registre a divergência antes de ajustar a estratégia.\n"
        "6. Quando houver correção segura, implemente-a, execute testes relevantes, build/lint quando aplicável e um smoke test do fluxo que falhou.\n"
        "7. Registre evidências objetivas do que mudou e por que a causa raiz foi removida.\n"
        "8. Só conclua com sucesso se o ambiente estiver apto a retestar a execução original. O worker do DevPilot recolocará automaticamente a execução original na fila para provar a correção.\n\n"
        f"FALHA DE ORIGEM\nCategoria: {category}\nCódigo: {code}\nMensagem: {message}\n"
        f"Causa técnica: {technical_message}\nExige autorização externa: {'sim' if authorization else 'não'}\n\n"
        f"CORREÇÃO PROPOSTA\n{recommended_action}\n\n"
        f"OBJETIVO ORIGINAL\nTítulo: {original_task.title}\n{_safe_original_prompt(original_task)}"
    )[:100_000]


def _activate_automatic_recovery(db: Session, recovery: Task) -> bool:
    if recovery.requires_approval:
        return False
    changed = False
    if recovery.approved_at is None:
        recovery.approved_at = datetime.now(timezone.utc)
        changed = True
    if recovery.status == TaskStatus.awaiting_approval:
        recovery.status = TaskStatus.queued
        recovery.updated_at = datetime.now(timezone.utc)
        changed = True
    return changed


def _reactivate_failed_automatic_recovery(
    db: Session,
    *,
    original_task: Task,
    recovery: Task,
    failure: dict,
    actor: str,
) -> bool:
    """Requeue a failed recovery only when the current evidence says no human authorization is needed.

    This is intentionally reached through an explicit recovery escalation. It repairs the terminal
    state shown by the game after a recovery task itself failed with a non-authorization error,
    without creating a duplicate recovery task or bypassing credential/permission gates.
    """
    if recovery.status not in {TaskStatus.failed, TaskStatus.blocked}:
        return False
    if recovery.requires_approval or bool(failure.get("requires_authorization")):
        return False

    failure = enrich_failure_from_run(latest_run_for_task(db, original_task.id), failure)
    now = datetime.now(timezone.utc)
    recovery.status = TaskStatus.queued
    recovery.requires_approval = False
    recovery.approved_at = recovery.approved_at or now
    recovery.updated_at = now
    recovery.prompt = (
        f"{str(recovery.prompt or '').rstrip()}\n\n"
        f"[failure-safe-retry:{now.isoformat()}]\n"
        "NOVA TENTATIVA SEGURA SOLICITADA PELO USUÁRIO\n"
        f"Causa exibida: {failure.get('technical_message') or failure.get('message')}.\n"
        f"Correção exibida: {failure.get('recommended_action')}.\n"
        "Reavalie a causa técnica no estado atual, execute a correção acima de forma verificável e reteste a tarefa original."
    )[:100_000]
    record(
        db,
        workspace_id=original_task.workspace_id,
        project_id=original_task.project_id,
        task_id=recovery.id,
        actor=actor,
        action="failure_recovery.safe_retry_requeued",
        outcome="queued",
        details={
            "original_task_id": original_task.id,
            "failure_category": failure.get("category", "unknown"),
            "failure_code": failure.get("code", "EXECUTION_FAILED"),
            "recommended_action": failure.get("recommended_action", ""),
        },
    )
    db.flush()
    return True


def ensure_failure_recovery_task(
    db: Session,
    *,
    original_task: Task,
    run: Run | None,
    failure: dict,
    actor: str = "worker",
) -> Task | None:
    if is_failure_recovery_task(original_task) or original_task.status not in {TaskStatus.failed, TaskStatus.blocked}:
        return None

    failure = enrich_failure_from_run(run, failure)
    existing = find_failure_recovery_task(db, original_task)
    if existing:
        # O worker apenas prepara o diagnóstico. A correção automática só entra
        # na fila quando o usuário aciona explicitamente "Corrigir e continuar".
        if actor == "owner" and _activate_automatic_recovery(db, existing):
            record(
                db,
                workspace_id=original_task.workspace_id,
                project_id=original_task.project_id,
                task_id=existing.id,
                actor=actor,
                action="failure_recovery.user_started",
                outcome="queued",
                details={
                    "original_task_id": original_task.id,
                    "reason": "explicit_fix_and_continue",
                    "recommended_action": failure.get("recommended_action", ""),
                },
            )
            db.flush()
        elif actor == "owner":
            _reactivate_failed_automatic_recovery(
                db,
                original_task=original_task,
                recovery=existing,
                failure=failure,
                actor=actor,
            )
        return existing

    requires_authorization = bool(failure.get("requires_authorization"))
    recovery = Task(
        workspace_id=original_task.workspace_id,
        owner_user_id=original_task.owner_user_id,
        project_id=original_task.project_id,
        title=f"Recuperação · {original_task.title}"[:240],
        prompt=recovery_prompt(original_task, run, failure),
        source="failure-recovery",
        # Mesmo quando a correção é segura, ela fica preparada e fora da fila.
        # O clique do usuário é o gatilho explícito para enfileirar a correção.
        status=TaskStatus.awaiting_approval,
        priority=min(100, max(85, int(original_task.priority or 50) + 20)),
        branch_name=original_task.branch_name or "",
        requires_approval=requires_authorization,
        approved_at=None,
    )
    db.add(recovery)
    db.flush()
    record(
        db,
        workspace_id=original_task.workspace_id,
        project_id=original_task.project_id,
        task_id=recovery.id,
        actor=actor,
        action="failure_recovery.prepared",
        outcome="awaiting_user_action" if not requires_authorization else "awaiting_approval",
        details={
            "original_task_id": original_task.id,
            "original_run_id": run.id if run else None,
            "failure_category": failure.get("category", "unknown"),
            "failure_code": failure.get("code", "EXECUTION_FAILED"),
            "requires_authorization": requires_authorization,
            "recommended_action": failure.get("recommended_action", ""),
            "automatic": False,
        },
    )
    return recovery


def resume_original_after_recovery(db: Session, *, recovery_task: Task, recovery_run: Run) -> Task | None:
    if recovery_run.status != "success" or not is_failure_recovery_task(recovery_task):
        return None
    original_id = recovery_origin_task_id(recovery_task)
    if not original_id:
        return None
    original = db.get(Task, original_id)
    if not original or original.workspace_id != recovery_task.workspace_id:
        return None
    if original.status not in {TaskStatus.failed, TaskStatus.blocked}:
        return original
    previous_status = original.status
    original.status = TaskStatus.queued
    original.updated_at = datetime.now(timezone.utc)
    record(
        db,
        workspace_id=original.workspace_id,
        project_id=original.project_id,
        task_id=original.id,
        actor="worker",
        action="failure_recovery.original_requeued",
        outcome="queued",
        details={
            "recovery_task_id": recovery_task.id,
            "recovery_run_id": recovery_run.id,
            "previous_status": previous_status.value,
            "proof_required": True,
        },
    )
    return original


def apply_user_guidance(db: Session, *, original_task: Task, instruction: str, actor: str = "owner") -> Task:
    recovery = find_failure_recovery_task(db, original_task)
    if not recovery:
        raise LookupError("Recovery task not found")
    if recovery.status in {TaskStatus.queued, TaskStatus.planning, TaskStatus.running, TaskStatus.review}:
        raise ValueError("Recovery task is already active")
    note = str(instruction or "").strip()
    if not note:
        raise ValueError("Instruction is required")
    timestamp = datetime.now(timezone.utc).isoformat()
    recovery.prompt = (
        f"{str(recovery.prompt or '').rstrip()}\n\n[failure-user-guidance:{timestamp}]\n"
        f"INTERVENÇÃO ASSISTIDA DO USUÁRIO\n{note}\n\n"
        "Retome a missão de recuperação considerando esta orientação. Confirme no ambiente real que a condição informada foi resolvida antes de concluir."
    )[:100_000]
    recovery.status = TaskStatus.queued
    recovery.requires_approval = False
    recovery.approved_at = datetime.now(timezone.utc)
    recovery.updated_at = datetime.now(timezone.utc)
    record(
        db,
        workspace_id=original_task.workspace_id,
        project_id=original_task.project_id,
        task_id=recovery.id,
        actor=actor,
        action="failure_recovery.user_guidance",
        outcome="queued",
        details={"original_task_id": original_task.id, "guided": True},
    )
    return recovery
