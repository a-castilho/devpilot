from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.ports import AppRecord
from app.models import Project


class SQLAlchemyAppCatalog:
    """Expose DevPilot projects as AgentOS applications without leaking credentials."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_apps(self, *, workspace_id: str) -> list[AppRecord]:
        projects = self.db.scalars(
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.name)
        ).all()
        return [
            AppRecord(
                id=project.id,
                name=project.name,
                slug=project.slug,
                description=project.description,
                repository_url=project.repository_url,
                status=str(project.status.value if hasattr(project.status, "value") else project.status),
            )
            for project in projects
        ]
