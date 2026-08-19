from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.app_connections import (
    AppConnectionConflict,
    AppConnectionRecord,
)
from app.agentos.application.ports import AppRecord
from app.agentos.domain.apps import KnownAppProfile
from app.agentos.models import AgentAppConnection
from app.models import Project


def _canonical_repository_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized.lower()


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

    def ensure_profile(
        self,
        *,
        workspace_id: str,
        profile: KnownAppProfile,
    ) -> AppConnectionRecord:
        project = self.db.scalar(
            select(Project).where(
                Project.workspace_id == workspace_id,
                Project.slug == profile.slug,
            )
        )
        created_project = False
        if project is None:
            project = Project(
                workspace_id=workspace_id,
                name=profile.name,
                slug=profile.slug,
                description=profile.description,
                repository_url=profile.repository_url,
                default_branch=profile.default_branch,
                agents_md="",
                codex_config="{}",
            )
            self.db.add(project)
            self.db.flush()
            created_project = True
        elif _canonical_repository_url(project.repository_url) != _canonical_repository_url(
            profile.repository_url
        ):
            raise AppConnectionConflict(
                f"Project slug {profile.slug} is already connected to another repository"
            )
        else:
            if not project.description:
                project.description = profile.description
            if not project.default_branch:
                project.default_branch = profile.default_branch

        connection = self.db.scalar(
            select(AgentAppConnection).where(
                AgentAppConnection.workspace_id == workspace_id,
                AgentAppConnection.profile_key == profile.key,
            )
        )
        if connection is None:
            connection = AgentAppConnection(
                workspace_id=workspace_id,
                project_id=project.id,
                profile_key=profile.key,
                profile_version=profile.profile_version,
                memory_version=0,
            )
            self.db.add(connection)
        elif connection.project_id != project.id:
            raise AppConnectionConflict(
                f"Profile {profile.key} is already connected to a different project"
            )
        else:
            connection.profile_version = profile.profile_version

        self.db.flush()
        return AppConnectionRecord(
            id=connection.id,
            project_id=connection.project_id,
            profile_key=connection.profile_key,
            profile_version=connection.profile_version,
            memory_version=connection.memory_version,
            created_project=created_project,
        )

    def mark_memory_version(
        self,
        *,
        connection_id: str,
        memory_version: int,
    ) -> AppConnectionRecord:
        connection = self.db.get(AgentAppConnection, connection_id)
        if connection is None:
            raise AppConnectionConflict("AgentOS app connection not found")
        connection.memory_version = memory_version
        self.db.flush()
        return AppConnectionRecord(
            id=connection.id,
            project_id=connection.project_id,
            profile_key=connection.profile_key,
            profile_version=connection.profile_version,
            memory_version=connection.memory_version,
        )

    def list_connections(self, *, workspace_id: str) -> list[AppConnectionRecord]:
        items = self.db.scalars(
            select(AgentAppConnection)
            .where(AgentAppConnection.workspace_id == workspace_id)
            .order_by(AgentAppConnection.profile_key)
        ).all()
        return [
            AppConnectionRecord(
                id=item.id,
                project_id=item.project_id,
                profile_key=item.profile_key,
                profile_version=item.profile_version,
                memory_version=item.memory_version,
            )
            for item in items
        ]
