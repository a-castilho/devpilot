import json
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import ProviderCredential, Project, ProjectStatus, Run, Task, TaskStatus
from app.services.audit import record
from app.services.bootstrap import bootstrap_title, build_bootstrap_prompt
from app.services.executor import execute_task
from app.services.vault import Vault


def provider_secret(db, workspace_id: str, provider: str) -> str:
    item = db.scalar(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == provider,
            ProviderCredential.enabled.is_(True),
        )
        .order_by(ProviderCredential.created_at.desc())
        .limit(1)
    )
    return Vault().decrypt(item.encrypted_secret) if item else ""


def enqueue_missing_bootstraps() -> int:
    created = 0
    with SessionLocal() as db:
        projects = db.scalars(select(Project).where(Project.status == ProjectStatus.active)).all()
        for project in projects:
            title = bootstrap_title(project)
            exists = db.scalar(
                select(Task.id).where(Task.project_id == project.id, Task.title == title)
            )
            if exists:
                continue
            try:
                config = json.loads(project.codex_config or "{}")
            except json.JSONDecodeError:
                config = {}
            if config.get("auto_start", True) is False:
                continue
            generate_agents_md = config.get("generate_agents_md", not bool(project.agents_md))
            task = Task(
                workspace_id=project.workspace_id,
                project_id=project.id,
                title=title,
                prompt=build_bootstrap_prompt(
                    project,
                    generate_agents_md=generate_agents_md,
                ),
                source="api",
                status=TaskStatus.queued,
                requires_approval=False,
                priority=80,
            )
            db.add(task)
            db.flush()
            record(
                db,
                workspace_id=project.workspace_id,
                project_id=project.id,
                task_id=task.id,
                actor="system",
                action="project.bootstrap_queued",
                details={"generate_agents_md": generate_agents_md, "backfill": True},
            )
            created += 1
        db.commit()
    return created


def process_one() -> bool:
    if not get_settings().execution_enabled:
        return False
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
        openai_api_key = provider_secret(db, task.workspace_id, "openai")
        if not openai_api_key:
            return False
        github_token = provider_secret(db, task.workspace_id, "github")
        task.status = TaskStatus.running
        run = Run(task_id=task.id)
        db.add(run)
        db.commit()
        try:
            result = execute_task(
                project,
                task,
                openai_api_key=openai_api_key,
                github_token=github_token,
            )
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
    enqueue_missing_bootstraps()
    while True:
        if not process_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
