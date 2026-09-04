import os
import re
import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Run, Task, TaskStatus
from app.rag.worker import process_one_rag_job
from app.services.audit import record
from app.services.runtime_preflight import WorkerRuntimeError, worker_runtime_paths
from app.services.task_orchestrator import TASK_RUNTIME, ensure_orchestrator_schema
from app.worker import process_one


_FAILURE_ORIGIN_RE = re.compile(r"\[failure-origin-task:([^\]]+)\]", re.IGNORECASE)
_STDIN_PLATFORM_FAILURE_MARKERS = (
    "reading additional input from stdin",
    "failed to read prompt from stdin",
    "no prompt provided via stdin",
)


def _startup_recovery_enabled() -> bool:
    return os.getenv("DEVPILOT_WORKER_RECOVER_RUNNING_ON_START", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _detach_worker_stdin() -> None:
    """Make the singleton worker fully non-interactive at the OS file-descriptor level.

    Codex `exec` treats a non-TTY stdin as optional additional prompt input. If a
    supervisor leaves fd 0 as an open pipe, Codex waits for EOF and can hang at
    "Reading additional input from stdin...". Replacing fd 0 with /dev/null makes
    every ordinary child process inherit an immediate EOF. Multimodal execution
    remains supported because its wrapper creates its own stdin pipe explicitly.
    """
    devnull_fd = os.open(os.devnull, os.O_RDONLY)
    if devnull_fd == 0:
        return
    try:
        os.dup2(devnull_fd, 0)
    finally:
        os.close(devnull_fd)


def _origin_task_id(recovery: Task) -> str:
    match = _FAILURE_ORIGIN_RE.search(str(recovery.prompt or ""))
    return match.group(1).strip() if match else ""


def _latest_run(db, task_id: str) -> Run | None:
    return db.scalar(
        select(Run)
        .where(Run.task_id == task_id)
        .order_by(Run.started_at.desc(), Run.attempt.desc())
        .limit(1)
    )


def _is_stdin_platform_failure(run: Run | None) -> bool:
    if not run:
        return False
    evidence = f"{run.summary or ''}\n{run.logs or ''}".casefold()
    return any(marker in evidence for marker in _STDIN_PLATFORM_FAILURE_MARKERS)


def _invalidate_obsolete_platform_recoveries() -> int:
    """Cancel recovery missions that were created for a DevPilot runner defect.

    Historical runs created before V103 persisted the Codex stdin hang as
    ``unknown`` and could therefore create a normal project recovery task. That
    task is invalid: changing the client repository cannot repair the DevPilot
    process stdin. On singleton-worker startup we retire those missions before
    orphan-lease recovery can accidentally put them back into the queue.
    """
    ensure_orchestrator_schema()
    obsolete = 0
    now = datetime.now(timezone.utc)
    active_statuses = {
        TaskStatus.queued,
        TaskStatus.planning,
        TaskStatus.running,
        TaskStatus.review,
        TaskStatus.awaiting_approval,
    }

    with SessionLocal() as db:
        recoveries = db.scalars(
            select(Task).where(
                Task.source == "failure-recovery",
                Task.status.in_(tuple(active_statuses)),
            )
        ).all()

        for recovery in recoveries:
            origin_id = _origin_task_id(recovery)
            if not origin_id or not _is_stdin_platform_failure(_latest_run(db, origin_id)):
                continue

            previous = recovery.status
            recovery.status = TaskStatus.failed
            recovery.updated_at = now
            db.execute(
                update(TASK_RUNTIME)
                .where(TASK_RUNTIME.c.task_id == recovery.id)
                .values(
                    state="canceled",
                    version=TASK_RUNTIME.c.version + 1,
                    claim_owner="",
                    lease_expires_at=None,
                    last_action="platform_recovery_obsoleted",
                    last_message=(
                        "Recovery cancelada: a causa pertence ao runner DevPilot (stdin), "
                        "não ao repositório do projeto. A tarefa original deve ser retestada."
                    ),
                    updated_at=now,
                )
            )
            record(
                db,
                workspace_id=recovery.workspace_id,
                project_id=recovery.project_id,
                task_id=recovery.id,
                actor="worker:startup",
                action="failure_recovery.platform_obsoleted",
                outcome="canceled",
                details={
                    "origin_task_id": origin_id,
                    "previous_status": (
                        previous.value if isinstance(previous, TaskStatus) else str(previous)
                    ),
                    "failure_code": "EXECUTOR_STDIN_BLOCKED",
                    "reason": "runner_failure_cannot_be_repaired_by_project_agent",
                },
            )
            obsolete += 1

        if obsolete:
            db.commit()

    return obsolete


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
    _detach_worker_stdin()
    print("[worker] stdin detached: /dev/null", flush=True)

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

    obsolete = _invalidate_obsolete_platform_recoveries()
    if obsolete:
        print(
            f"[worker] canceled {obsolete} obsolete project recovery task(s) for platform stdin failures",
            flush=True,
        )

    # This intentionally runs after platform-recovery invalidation. Otherwise a
    # stale recovery that happened to be running at container shutdown would be
    # resurrected as queued before we can retire it.
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
