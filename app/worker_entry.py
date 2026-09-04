import os
import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Task, TaskStatus
from app.rag.worker import process_one_rag_job
from app.services.audit import record
from app.services.runtime_preflight import WorkerRuntimeError, worker_runtime_paths
from app.services.task_orchestrator import TASK_RUNTIME, ensure_orchestrator_schema
from app.worker import process_one


def _startup_recovery_enabled() -> bool:
    return os.getenv("DEVPILOT_WORKER_RECOVER_RUNNING_ON_START", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _recover_orphaned_running_tasks() -> int:
    """Requeue tasks left as running by the previous singleton worker instance.

    Docker Compose runs a single DevPilot task worker. When that container is
    recreated, an in-flight task can remain marked as running with a long lease,
    even though the process that owned the lease no longer exists. In singleton
    mode it is safe to return those worker-owned tasks to the queue on startup.
    """
    if not _startup_recovery_enabled():
        return 0

    ensure_orchestrator_schema()
    recovered = 0
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        task_ids = db.execute(
            select(TASK_RUNTIME.c.task_id).where(
                TASK_RUNTIME.c.state == "running",
                TASK_RUNTIME.c.claim_owner.like("worker:%"),
            )
        ).scalars().all()

        for task_id in task_ids:
            task = db.get(Task, task_id)
            if task is None or task.status != TaskStatus.running:
                continue

            task.status = TaskStatus.queued
            db.execute(
                update(TASK_RUNTIME)
                .where(TASK_RUNTIME.c.task_id == task.id)
                .values(
                    state="queued",
                    version=TASK_RUNTIME.c.version + 1,
                    claim_owner="",
                    lease_expires_at=None,
                    last_action="worker_restart_recovered",
                    last_message=(
                        "Worker anterior foi reiniciado; execução órfã devolvida à fila "
                        "sem apagar runs ou evidências."
                    ),
                    updated_at=now,
                )
            )
            record(
                db,
                workspace_id=task.workspace_id,
                project_id=task.project_id,
                task_id=task.id,
                actor="worker:startup",
                action="task.orchestrator.worker_restart_recovered",
                outcome="success",
                details={"previous_state": "running", "new_state": "queued"},
            )
            recovered += 1

        if recovered:
            db.commit()

    return recovered


def main() -> None:
    try:
        runtime = worker_runtime_paths()
    except WorkerRuntimeError as error:
        print(f"[worker] PRECHECK FAILED: {error}", flush=True)
        raise SystemExit(78) from error

    print(
        "[worker] runtime OK: "
        + ", ".join(f"{tool}={path}" for tool, path in runtime.items()),
        flush=True,
    )

    recovered = _recover_orphaned_running_tasks()
    if recovered:
        print(
            f"[worker] recovered {recovered} orphaned running task(s) after restart",
            flush=True,
        )

    while True:
        rag_processed = False
        with SessionLocal() as db:
            rag_processed = process_one_rag_job(db)
        task_processed = process_one()
        if not rag_processed and not task_processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
