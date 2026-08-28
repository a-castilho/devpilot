from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Project, Run, Task, TaskStatus, User


RADAR_TASK_TITLE = "Radar Regula AÍ — jornal regulatório automático"
RADAR_PR_URL = "https://github.com/a-castilho/regulaai/pull/79"
RADAR_BRANCH = "feature/radar-editorial-78"
RADAR_COMMIT_SHA = "ccc8d663b720de91e158ea6a88369ce50e627c20"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def bootstrap_regulaai_radar_admin_task(engine: Engine) -> bool:
    """Persist the historical Radar Regula AÍ delivery in the Super Admin queue.

    This bootstrap is intentionally idempotent and opportunistic: if the Regula AÍ
    project or a SUPER_ADMIN is not present yet, startup continues normally and a
    later restart can register the task after project provisioning.
    """
    with Session(engine) as db:
        project = db.scalar(
            select(Project)
            .where(
                or_(
                    Project.slug == "regulaai",
                    Project.repository_url.ilike("%a-castilho/regulaai%"),
                )
            )
            .order_by(Project.created_at.asc(), Project.id.asc())
            .limit(1)
        )
        if project is None:
            return False

        super_admin = db.scalar(
            select(User)
            .where(
                User.workspace_id == project.workspace_id,
                User.role == "SUPER_ADMIN",
                User.active.is_(True),
            )
            .order_by(User.created_at.asc(), User.id.asc())
            .limit(1)
        )
        if super_admin is None:
            return False

        task = db.scalar(
            select(Task)
            .where(
                Task.workspace_id == project.workspace_id,
                Task.project_id == project.id,
                Task.owner_user_id == super_admin.id,
                Task.title == RADAR_TASK_TITLE,
            )
            .limit(1)
        )

        now = _now()
        created = False
        if task is None:
            task = Task(
                workspace_id=project.workspace_id,
                owner_user_id=super_admin.id,
                project_id=project.id,
                title=RADAR_TASK_TITLE,
                prompt=(
                    "Entrega histórica registrada pelo DevPilot: implementar o Radar "
                    "Regula AÍ como jornal regulatório automático, alimentado pelos "
                    "RegulatoryEvent existentes, com sincronização idempotente, "
                    "score editorial, publicação conservadora, API pública, página "
                    "radar.html, SEO, testes e documentação. Issue Regula AÍ #78; "
                    "PR Regula AÍ #79."
                ),
                source="api",
                status=TaskStatus.completed,
                priority=90,
                branch_name=RADAR_BRANCH,
                requires_approval=False,
                approved_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(task)
            db.flush()
            created = True
        else:
            task.status = TaskStatus.completed
            task.branch_name = task.branch_name or RADAR_BRANCH
            task.requires_approval = False
            task.approved_at = task.approved_at or now
            task.updated_at = now

        run = db.scalar(
            select(Run)
            .where(
                Run.task_id == task.id,
                Run.pull_request_url == RADAR_PR_URL,
            )
            .limit(1)
        )
        if run is None:
            db.add(
                Run(
                    task_id=task.id,
                    attempt=1,
                    status="completed",
                    summary=(
                        "Radar Regula AÍ implementado e entregue no PR #79. "
                        "O CI do repositório Regula AÍ ficou bloqueado por falha de "
                        "provisionamento do GitHub Actions antes dos steps; a entrega "
                        "foi preservada em PR sem merge automático."
                    ),
                    logs="bootstrap: historical delivery registered by DevPilot",
                    commit_sha=RADAR_COMMIT_SHA,
                    pull_request_url=RADAR_PR_URL,
                    started_at=now,
                    finished_at=now,
                )
            )

        db.commit()
        return created
