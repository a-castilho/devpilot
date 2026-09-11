from __future__ import annotations

from sqlalchemy import select

from app.models import Task, TaskStatus
from app.services import failure_recovery
from app.services import task_orchestrator

# A worker saudável renova o lease continuamente. Duas horas deixavam processos
# mortos aparentando estar ativos e segurando a fila por tempo demais.
task_orchestrator.LEASE_SECONDS = 1200
task_orchestrator.LEASE_RENEW_INTERVAL_SECONDS = 30

_ORIGINAL_ENSURE_FAILURE_RECOVERY_TASK = failure_recovery.ensure_failure_recovery_task
_ACTIVE_TASK_STATUSES = {
    TaskStatus.queued,
    TaskStatus.planning,
    TaskStatus.running,
    TaskStatus.review,
    TaskStatus.awaiting_approval,
}
_TERMINAL_RUNTIME_STATES = {"archived", "completed", "canceled"}


def _active_project_recovery(db, original_task: Task) -> Task | None:
    """Return one active recovery for the same project+mission title.

    Duplicate game/task submissions can have different task ids while describing
    the same mission. Recovery is therefore idempotent at project+title level,
    not only at origin-task-id level.
    """
    title = f"Recuperação · {original_task.title}"[:240]
    candidates = list(
        db.scalars(
            select(Task)
            .where(
                Task.workspace_id == original_task.workspace_id,
                Task.project_id == original_task.project_id,
                Task.source == "failure-recovery",
                Task.title == title,
                Task.status.in_(tuple(_ACTIVE_TASK_STATUSES)),
            )
            .order_by(Task.updated_at.desc(), Task.created_at.desc())
        ).all()
    )
    for candidate in candidates:
        runtime_state = db.scalar(
            select(task_orchestrator.TASK_RUNTIME.c.state).where(
                task_orchestrator.TASK_RUNTIME.c.task_id == candidate.id
            )
        )
        if runtime_state in _TERMINAL_RUNTIME_STATES:
            continue
        return candidate
    return None


def _ensure_failure_recovery_task(*args, **kwargs):
    db = kwargs.get("db") or (args[0] if args else None)
    original_task = kwargs.get("original_task")
    if db is not None and original_task is not None:
        existing = _active_project_recovery(db, original_task)
        if existing is not None:
            return existing
    return _ORIGINAL_ENSURE_FAILURE_RECOVERY_TASK(*args, **kwargs)


def install() -> None:
    if getattr(failure_recovery.ensure_failure_recovery_task, "_devpilot_queue_guard", False):
        return
    _ensure_failure_recovery_task._devpilot_queue_guard = True
    failure_recovery.ensure_failure_recovery_task = _ensure_failure_recovery_task


install()
