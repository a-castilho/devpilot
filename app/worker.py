import json
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project, Run, Task, TaskStatus
from app.services.audit import record
from app.services.executor import execute_task
from app.services.runtime_preflight import WorkerRuntimeError, worker_runtime_paths


def process_one() -> bool:
    with SessionLocal() as db:
        task = db.scalar(
            select(Task)
            .where(Task.status == TaskStatus.queued)
            .order_by(Task.priority.desc(), Task.created_at)
            .limit(1)
        )
        if not task:
            return False
        project = db.get(Project, task.project_id)
        task.status = TaskStatus.running
        run = Run(task_id=task.id)
        db.add(run)
        db.commit()
        try:
            result = execute_task(project, task)
            run.status = "success" if result.get("exit_code", 0) == 0 else "failed"
            run.summary = result.get("summary", "Execution completed")
            run.logs = json.dumps(result, ensure_ascii=False)
            task.status = TaskStatus.review if run.status == "success" else TaskStatus.failed
            outcome = run.status
        except Exception as error:
            run.status = "failed"
            run.summary = str(error)
            task.status = TaskStatus.failed
            outcome = "failed"
        run.finished_at = datetime.now(timezone.utc)
        record(
            db,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor="worker",
            action="task.executed",
            outcome=outcome,
            details={"run_id": run.id},
        )
        db.commit()
        return True


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

    while True:
        if not process_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
