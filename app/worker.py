import json
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Project, Run, Task, TaskStatus
from app.services.audit import record
from app.services.executor import execute_task


def process_one() -> bool:
    if not get_settings().execution_enabled:
        return False
    with SessionLocal() as db:
        task = db.scalar(select(Task).where(Task.status == TaskStatus.queued).order_by(Task.priority.desc(), Task.created_at).limit(1))
        if not task:
            return False
        project = db.get(Project, task.project_id)
        task.status = TaskStatus.running
        run = Run(task_id=task.id)
        db.add(run)
        db.commit()
        try:
            result = execute_task(project, task)
            if result.get("mode") == "dry-run":
                run.status = "blocked"
                run.summary = result.get("summary", "Execution is disabled")
                task.status = TaskStatus.blocked
            else:
                run.status = "success" if result.get("exit_code", 0) == 0 else "failed"
                run.summary = result.get("summary", "Execution completed")
                task.status = TaskStatus.review if run.status == "success" else TaskStatus.failed
            if run.status == "success" and result.get("generated_agents_md"):
                project.agents_md = result["generated_agents_md"]
            run.logs = json.dumps(result, ensure_ascii=False)
            outcome = run.status
        except Exception as error:
            run.status = "failed"
            run.summary = str(error)
            task.status = TaskStatus.failed
            outcome = "failed"
        run.finished_at = datetime.now(timezone.utc)
        record(db, workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor="worker", action="task.executed", outcome=outcome, details={"run_id": run.id})
        db.commit()
        return True


def main() -> None:
    while True:
        if not process_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
