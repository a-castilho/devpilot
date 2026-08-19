from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from app.agentos.application.ports import EventBusPort, KnowledgePort, UnitOfWorkPort
from app.agentos.domain.apps import KNOWN_APP_PROFILES, KnownAppProfile
from app.agentos.domain.events import DomainEvent
from app.agentos.domain.platform import memory_namespace


class AppConnectionConflict(RuntimeError):
    """Raised when a known app slug is already bound to a different repository."""


@dataclass(frozen=True, slots=True)
class AppConnectionRecord:
    id: str
    project_id: str
    profile_key: str
    profile_version: int
    memory_version: int
    created_project: bool = False


class AppConnectionCatalogPort(Protocol):
    def ensure_profile(
        self,
        *,
        workspace_id: str,
        profile: KnownAppProfile,
    ) -> AppConnectionRecord: ...

    def mark_memory_version(
        self,
        *,
        connection_id: str,
        memory_version: int,
    ) -> AppConnectionRecord: ...

    def list_connections(self, *, workspace_id: str) -> list[AppConnectionRecord]: ...


class KnownAppConnectionService:
    """Connect curated product repositories to AppHub and project-scoped MemoryOS."""

    def __init__(
        self,
        *,
        catalog: AppConnectionCatalogPort,
        knowledge: KnowledgePort,
        events: EventBusPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self.catalog = catalog
        self.knowledge = knowledge
        self.events = events
        self.uow = uow

    @staticmethod
    def profiles() -> list[dict[str, Any]]:
        return [asdict(profile) for profile in KNOWN_APP_PROFILES.values()]

    def list_connections(self, *, workspace_id: str) -> list[AppConnectionRecord]:
        return self.catalog.list_connections(workspace_id=workspace_id)

    def connect(
        self,
        *,
        workspace_id: str,
        keys: list[str] | None = None,
        seed_memory: bool = True,
    ) -> list[dict[str, Any]]:
        requested = keys or list(KNOWN_APP_PROFILES)
        normalized = list(dict.fromkeys(key.strip().lower() for key in requested if key.strip()))
        unknown = [key for key in normalized if key not in KNOWN_APP_PROFILES]
        if unknown:
            raise ValueError(f"Unknown AgentOS app profiles: {', '.join(unknown)}")

        results: list[dict[str, Any]] = []
        try:
            for key in normalized:
                profile = KNOWN_APP_PROFILES[key]
                connection = self.catalog.ensure_profile(
                    workspace_id=workspace_id,
                    profile=profile,
                )
                created_project = connection.created_project
                memory_seeded = False
                if seed_memory and connection.memory_version < profile.memory_version:
                    self.knowledge.ingest(
                        workspace_id=workspace_id,
                        project_id=connection.project_id,
                        namespace=memory_namespace("project", project_id=connection.project_id),
                        source=f"agentos://known-app/{profile.key}/v{profile.memory_version}",
                        content=profile.memory_document(),
                        metadata={
                            "kind": "known-app-profile",
                            "profile_key": profile.key,
                            "profile_version": profile.profile_version,
                            "memory_version": profile.memory_version,
                            "recommended_agents": list(profile.recommended_agents),
                        },
                    )
                    connection = self.catalog.mark_memory_version(
                        connection_id=connection.id,
                        memory_version=profile.memory_version,
                    )
                    memory_seeded = True

                self.events.publish(
                    DomainEvent(
                        name="agentos.app.connected",
                        workspace_id=workspace_id,
                        project_id=connection.project_id,
                        payload={
                            "profile_key": profile.key,
                            "repository_url": profile.repository_url,
                            "created_project": created_project,
                            "memory_seeded": memory_seeded,
                            "profile_version": profile.profile_version,
                            "memory_version": connection.memory_version,
                        },
                    )
                )
                results.append(
                    {
                        "profile_key": profile.key,
                        "name": profile.name,
                        "project_id": connection.project_id,
                        "repository_url": profile.repository_url,
                        "created_project": created_project,
                        "memory_seeded": memory_seeded,
                        "profile_version": connection.profile_version,
                        "memory_version": connection.memory_version,
                        "recommended_agents": list(profile.recommended_agents),
                    }
                )
            self.uow.commit()
            return results
        except Exception:
            self.uow.rollback()
            raise
