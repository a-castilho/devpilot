from __future__ import annotations

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
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}\n\n[conteúdo original truncado pelo fluxo de recuperação]"


def recovery_prompt(original_task: Task, run: Run | None, failure: dict) -> str:
    category = str(failure.get("category") or "unknown")
    code = str(failure.get("code") or "EXECUTION_FAILED")
    message = str(failure.get("message") or "Falha sem mensagem detalhada.")
    authorization = bool(failure.get("requires_authorization"))
    run_id = run.id if run else ""

    return (
        f"{RECOVERY_MARKER}\n"
        "[DEVPILOT_MODE=fix]\n"
        f"[failure-origin-task:{original_task.id}]\n"
        f"[failure-origin-run:{run_id}]\n"
        f"[failure-category:{category}]\n"
        f"[failure-code:{code}]\n"
        f"[failure-requires-authorization:{str(authorization).lower()}]\n\n"
        "MISSÃO DE RECUPERAÇÃO\n"
        "Uma execução anterior falhou depois do ciclo normal de autocorreção. Sua função é remover a causa raiz de forma verificável, sem repetir cegamente a mesma tentativa.\n\n"
        "PROTOCOLO OBRIGATÓRIO\n"
        "1. Leia AGENTS.md, documentação aplicável e o estado real do repositório antes de alterar qualquer coisa.\n"
        "2. Use a falha abaixo como evidência inicial, mas confirme a causa raiz no ambiente atual.\n"
        "3. Preserve código estável, dados e credenciais. Não force permissões, não apague dados e não contorne autorizações.\n"
        "4. Se a causa depender de credencial, autenticação, permissão ou decisão humana ainda ausente, NÃO improvise. Pare e descreva exatamente a intervenção necessária.\n"
        "5. Quando houver correção segura, implemente-a, execute testes relevantes, build/lint quando aplicável e um smoke test do fluxo que falhou.\n"
        "6. Registre evidências objetivas do que mudou e por que a causa raiz foi removida.\n"
        "7. Só conclua com sucesso se o ambiente estiver apto a retestar a execução original. O worker do DevPilot recolocará automaticamente a execução original na fila para provar a correção.\n\n"
        "FALHA DE ORIGEM\n"
        f"Categoria: {category}\n"
        f"Código: {code}\n"
        f"Mensagem: {message}\n"
        f"Exige autorização externa: {'sim' if authorization else 'não'}\n\n"
        "OBJETIVO ORIGINAL\n"
        f"Título: {original_task.title}\n"
        f"{_safe_original_prompt(original_task)}"
    )[:100_000]


def ensure_failure_recovery_task(
    db: Session,
    *,
    original_task: Task,
    run: Run | None,
    failure: dict,
    actor: str = "worker",
) -> Task | None:
    if is_failure_recovery_task(original_task):
        return None
    if original_task.status not in {TaskStatus.failed, TaskStatus.blocked}:
        return None

    existing = find_failure_recovery_task(db, original_task)
    if existing:
        return existing

    requires_authorization = bool(failure.get("requires_authorization"))
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
            "automatic": actor == "worker",
        },
    )
    return recovery


def resume_original_after_recovery(
    db: Session,
    *,
    recovery_task: Task,
    recovery_run: Run,
) -> Task | None:
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


def apply_user_guidance(
    db: Session,
    *,
    original_task: Task,
    instruction: str,
    actor: str = "owner",
) -> Task:
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
        f"{str(recovery.prompt or '').rstrip()}\n\n"
        f"[failure-user-guidance:{timestamp}]\n"
        "INTERVENÇÃO ASSISTIDA DO USUÁRIO\n"
        f"{note}\n\n"
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
