from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Run, Task, TaskStatus
from app.services.audit import record

RECOVERY_MARKER = "[DEVPILOT_FAILURE_RECOVERY_V1]"
_ORIGIN_RE = re.compile(r"\[failure-origin-task:([^\]]+)\]", re.IGNORECASE)
_SYSTEM_MANAGED_RECOVERY_CATEGORIES = {"github_auth"}


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


def _requires_external_authorization(failure: dict) -> bool:
    """Only a proven external boundary may stop automatic recovery.

    GitHub access is system-managed in DevPilot: the recovery layer must first use the
    already registered credentials/fallbacks instead of inheriting a stale legacy
    `requires_authorization=true` flag from an old run.
    """
    category = str(failure.get("category") or "unknown").strip().lower()
    if category in _SYSTEM_MANAGED_RECOVERY_CATEGORIES:
        return False
    return bool(failure.get("requires_authorization"))


def recovery_prompt(original_task: Task, run: Run | None, failure: dict) -> str:
    category = str(failure.get("category") or "unknown")
    code = str(failure.get("code") or "EXECUTION_FAILED")
    message = str(failure.get("message") or "Falha sem mensagem detalhada.")
    authorization = _requires_external_authorization(failure)
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
        "4. Se a causa envolver credencial, autenticação, permissão ou dependência externa, esgote primeiro as alternativas automáticas seguras já autorizadas e disponíveis no DevPilot, como credenciais cadastradas, sessão administrada, checkout válido, retry controlado ou reconstrução reversível. Só declare intervenção humana em última instância, quando houver uma fronteira externa comprovada. Não invente acesso nem contorne autorização.\n"
        "5. Quando houver correção segura, implemente-a, execute testes relevantes, build/lint quando aplicável e um smoke test do fluxo que falhou.\n"
        "6. Informe objetivamente o diagnóstico, a solução aplicada, as evidências e qualquer limitação remanescente sem interromper a esteira por um alerta meramente informativo.\n"
        "7. Só conclua com sucesso se o ambiente estiver apto a retestar a execução original. O worker do DevPilot recolocará automaticamente a execução original na fila para provar a correção e seguir para a próxima etapa.\n\n"
        f"FALHA DE ORIGEM\nCategoria: {category}\nCódigo: {code}\nMensagem: {message}\nExige autorização externa: {'sim' if authorization else 'não'}\n\n"
        f"OBJETIVO ORIGINAL\nTítulo: {original_task.title}\n{_safe_original_prompt(original_task)}"
    )[:100_000]


def _activate_automatic_recovery(
    db: Session,
    recovery: Task,
    *,
    allow_gate_repair: bool = False,
) -> bool:
    if recovery.requires_approval and not allow_gate_repair:
        return False

    changed = False
    now = datetime.now(timezone.utc)
    if recovery.requires_approval and allow_gate_repair:
        recovery.requires_approval = False
        changed = True
    if recovery.approved_at is None:
        recovery.approved_at = now
        changed = True
    if recovery.status == TaskStatus.awaiting_approval:
        recovery.status = TaskStatus.queued
        recovery.updated_at = now
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
    """Requeue a failed recovery only when current evidence permits automation."""
    if recovery.status not in {TaskStatus.failed, TaskStatus.blocked}:
        return False

    requires_authorization = _requires_external_authorization(failure)
    if requires_authorization:
        return False

    now = datetime.now(timezone.utc)
    recovery.status = TaskStatus.queued
    recovery.requires_approval = False
    recovery.approved_at = recovery.approved_at or now
    recovery.updated_at = now
    recovery.prompt = (
        f"{str(recovery.prompt or '').rstrip()}\n\n"
        f"[failure-safe-retry:{now.isoformat()}]\n"
        "NOVA TENTATIVA SEGURA SOLICITADA\n"
        "A recuperação anterior falhou sem evidência atual de uma fronteira externa que exija ação humana. "
        "Reavalie a causa técnica no estado atual, esgote alternativas automáticas seguras, implemente somente uma correção verificável e reteste a tarefa original."
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
            "automation_first": True,
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

    requires_authorization = _requires_external_authorization(failure)
    raw_requires_authorization = bool(failure.get("requires_authorization"))
    system_managed_override = raw_requires_authorization and not requires_authorization

    existing = find_failure_recovery_task(db, original_task)
    if existing:
        if _activate_automatic_recovery(
            db,
            existing,
            allow_gate_repair=not requires_authorization,
        ):
            record(
                db,
                workspace_id=original_task.workspace_id,
                project_id=original_task.project_id,
                task_id=existing.id,
                actor=actor,
                action="failure_recovery.automatic_gate_repaired",
                outcome="queued",
                details={
                    "original_task_id": original_task.id,
                    "reason": (
                        "stale_system_managed_authorization_gate"
                        if system_managed_override
                        else "awaiting_approval_without_required_authorization"
                    ),
                    "failure_category": failure.get("category", "unknown"),
                    "automation_first": True,
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

    recovery = Task(
        workspace_id=original_task.workspace_id,
        owner_user_id=original_task.owner_user_id,
        project_id=original_task.project_id,
        title=f"Recuperação · {original_task.title}"[:240],
        prompt=recovery_prompt(original_task, run, failure),
        source="failure-recovery",
        status=TaskStatus.awaiting_approval if requires_authorization else TaskStatus.queued,
        priority=min(100, max(85, int(original_task.priority or 50) + 20)),
        branch_name=original_task.branch_name or "",
        requires_approval=requires_authorization,
        approved_at=None if requires_authorization else datetime.now(timezone.utc),
    )
    db.add(recovery)
    db.flush()
    record(
        db,
        workspace_id=original_task.workspace_id,
        project_id=original_task.project_id,
        task_id=recovery.id,
        actor=actor,
        action="failure_recovery.created",
        outcome=recovery.status.value,
        details={
            "original_task_id": original_task.id,
            "original_run_id": run.id if run else None,
            "failure_category": failure.get("category", "unknown"),
            "failure_code": failure.get("code", "EXECUTION_FAILED"),
            "requires_authorization": requires_authorization,
            "raw_requires_authorization": raw_requires_authorization,
            "system_managed_override": system_managed_override,
            "automatic": actor == "worker",
            "automation_first": True,
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
            "pipeline_continuation": True,
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
