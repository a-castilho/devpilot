from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Run, Task, TaskStatus
from app.services.audit import record
from app.services.task_orchestrator import TASK_RUNTIME, ensure_orchestrator_schema


STALE_DELIVERY_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def recover_stale_delivery_claims() -> int:
    """Return abandoned final-delivery repair tasks to the queue.

    This intentionally targets only ``delivery-recovery`` tasks. Normal development
    tasks keep the existing generic lease contract. A live worker updates the runtime
    heartbeat while supervising Codex; a five-minute-old heartbeat after a Render
    restart is treated as an abandoned delivery claim.
    """
    ensure_orchestrator_schema()
    point = _now()
    cutoff = point - timedelta(seconds=STALE_DELIVERY_SECONDS)
    recovered = 0

    with SessionLocal() as db:
        rows = db.execute(
            select(
                Task.id,
                Task.workspace_id,
                Task.project_id,
                TASK_RUNTIME.c.claim_owner,
                TASK_RUNTIME.c.updated_at,
            )
            .join(TASK_RUNTIME, TASK_RUNTIME.c.task_id == Task.id)
            .where(
                Task.source == "delivery-recovery",
                Task.status == TaskStatus.running,
                TASK_RUNTIME.c.state == "running",
                TASK_RUNTIME.c.updated_at < cutoff,
            )
        ).mappings().all()

        for row in rows:
            task_id = str(row["id"])
            claim_owner = str(row["claim_owner"] or "")
            observed_updated_at = row["updated_at"]

            runtime_result = db.execute(
                update(TASK_RUNTIME)
                .where(
                    TASK_RUNTIME.c.task_id == task_id,
                    TASK_RUNTIME.c.state == "running",
                    TASK_RUNTIME.c.claim_owner == claim_owner,
                    TASK_RUNTIME.c.updated_at == observed_updated_at,
                )
                .values(
                    state="queued",
                    version=TASK_RUNTIME.c.version + 1,
                    claim_owner="",
                    lease_expires_at=None,
                    last_action="delivery_restart_recovered",
                    last_message="Execução de entrega sem heartbeat após restart; devolvida à fila.",
                    updated_at=point,
                )
            )
            if int(runtime_result.rowcount or 0) != 1:
                continue

            task_result = db.execute(
                update(Task)
                .where(Task.id == task_id, Task.status == TaskStatus.running)
                .values(status=TaskStatus.queued, updated_at=point)
            )
            if int(task_result.rowcount or 0) != 1:
                db.rollback()
                continue

            # Close the abandoned attempt so run history never pretends it is still active.
            db.execute(
                update(Run)
                .where(Run.task_id == task_id, Run.status == "started", Run.finished_at.is_(None))
                .values(
                    status="failed",
                    finished_at=point,
                    summary="Execução interrompida por restart do worker; tarefa reenfileirada automaticamente.",
                )
            )
            record(
                db,
                workspace_id=str(row["workspace_id"]),
                project_id=str(row["project_id"]),
                task_id=task_id,
                actor="embedded-worker",
                action="task.delivery_restart_recovered",
                outcome="queued",
                details={
                    "claim_owner": claim_owner,
                    "stale_seconds": STALE_DELIVERY_SECONDS,
                    "fenced_by_updated_at": True,
                },
            )
            db.commit()
            recovered += 1

    return recovered
