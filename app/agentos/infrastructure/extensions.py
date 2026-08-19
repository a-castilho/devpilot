from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.extensions import ExtensionActivationPort, ExtensionActivationRecord
from app.agentos.models import AgentExtensionActivation


class SQLAlchemyExtensionActivations(ExtensionActivationPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _record(item: AgentExtensionActivation) -> ExtensionActivationRecord:
        return ExtensionActivationRecord(
            project_id=item.project_id,
            extension_key=item.extension_key,
            extension_version=item.extension_version,
            enabled=bool(item.enabled),
        )

    def list(
        self,
        *,
        workspace_id: str,
        project_id: str | None = None,
    ) -> list[ExtensionActivationRecord]:
        statement = select(AgentExtensionActivation).where(
            AgentExtensionActivation.workspace_id == workspace_id
        )
        if project_id is not None:
            statement = statement.where(AgentExtensionActivation.project_id == project_id)
        items = self.db.scalars(
            statement.order_by(
                AgentExtensionActivation.project_id,
                AgentExtensionActivation.extension_key,
            )
        ).all()
        return [self._record(item) for item in items]

    def set_enabled(
        self,
        *,
        workspace_id: str,
        project_id: str,
        extension_key: str,
        extension_version: int,
        enabled: bool,
    ) -> ExtensionActivationRecord:
        item = self.db.scalar(
            select(AgentExtensionActivation).where(
                AgentExtensionActivation.workspace_id == workspace_id,
                AgentExtensionActivation.project_id == project_id,
                AgentExtensionActivation.extension_key == extension_key,
            )
        )
        if item is None:
            item = AgentExtensionActivation(
                workspace_id=workspace_id,
                project_id=project_id,
                extension_key=extension_key,
                extension_version=extension_version,
                enabled=1 if enabled else 0,
            )
            self.db.add(item)
        else:
            item.extension_version = extension_version
            item.enabled = 1 if enabled else 0
        self.db.flush()
        return self._record(item)
