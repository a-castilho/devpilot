from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from app.agentos.domain.events import DomainEvent
from app.agentos.domain.extensions import EXTENSION_CATALOG
from app.agentos.application.ports import EventBusPort, UnitOfWorkPort


@dataclass(frozen=True, slots=True)
class ExtensionActivationRecord:
    project_id: str
    extension_key: str
    extension_version: int
    enabled: bool


class ExtensionActivationPort(Protocol):
    def list(self, *, workspace_id: str, project_id: str | None = None) -> list[ExtensionActivationRecord]: ...

    def set_enabled(
        self,
        *,
        workspace_id: str,
        project_id: str,
        extension_key: str,
        extension_version: int,
        enabled: bool,
    ) -> ExtensionActivationRecord: ...


class ExtensionMarketplaceService:
    """Safe built-in marketplace: activates reviewed packs, never downloads executable code."""

    def __init__(
        self,
        *,
        activations: ExtensionActivationPort,
        events: EventBusPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self.activations = activations
        self.events = events
        self.uow = uow

    @staticmethod
    def catalog() -> list[dict]:
        return [asdict(spec) for spec in EXTENSION_CATALOG.values()]

    def list_activations(self, *, workspace_id: str, project_id: str | None = None) -> list[dict]:
        return [asdict(item) for item in self.activations.list(workspace_id=workspace_id, project_id=project_id)]

    def set_enabled(
        self,
        *,
        workspace_id: str,
        project_id: str,
        extension_key: str,
        enabled: bool,
    ) -> dict:
        spec = EXTENSION_CATALOG.get(extension_key)
        if spec is None:
            raise ValueError(f"Unknown AgentOS extension: {extension_key}")
        try:
            record = self.activations.set_enabled(
                workspace_id=workspace_id,
                project_id=project_id,
                extension_key=extension_key,
                extension_version=spec.version,
                enabled=enabled,
            )
            self.events.publish(
                DomainEvent(
                    name="agentos.extension.enabled" if enabled else "agentos.extension.disabled",
                    workspace_id=workspace_id,
                    project_id=project_id,
                    payload={
                        "extension_key": extension_key,
                        "extension_version": spec.version,
                        "agents": list(spec.agents),
                        "tools": list(spec.tools),
                    },
                )
            )
            self.uow.commit()
            return asdict(record)
        except Exception:
            self.uow.rollback()
            raise
