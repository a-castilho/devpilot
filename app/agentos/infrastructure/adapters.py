from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.errors import ModelUnavailable as ApplicationModelUnavailable
from app.agentos.application.planning import PlanningStrategyFactory
from app.agentos.application.ports import GoalRecord, KnowledgeIngestResult
from app.agentos.contracts import AgentPlan
from app.agentos.domain.events import DomainEvent
from app.agentos.llm import LLMClient, ModelUnavailable as ProviderModelUnavailable
from app.agentos.models import AgentGoal
from app.agentos.rag import ingest as rag_ingest
from app.agentos.rag import search as rag_search
from app.services.audit import record


class PlannerAdapter:
    """Adapter from the application planner port to a selectable planning strategy."""

    def plan(self, objective: str, *, mode: str = "resource-light") -> AgentPlan:
        return PlanningStrategyFactory.create(mode).plan(objective)


class SQLAlchemyGoalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _record(item: AgentGoal) -> GoalRecord:
        return GoalRecord(
            id=item.id,
            workspace_id=item.workspace_id,
            project_id=item.project_id,
            title=item.title,
            objective=item.objective,
            status=item.status,
            plan=AgentPlan.model_validate_json(item.plan_json),
            created_at=item.created_at,
        )

    def add(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        title: str,
        objective: str,
        plan: AgentPlan,
    ) -> GoalRecord:
        item = AgentGoal(
            workspace_id=workspace_id,
            project_id=project_id,
            title=title,
            objective=objective,
            status="planned",
            plan_json=plan.model_dump_json(),
        )
        self.db.add(item)
        self.db.flush()
        return self._record(item)

    def get(self, *, workspace_id: str, goal_id: str) -> GoalRecord | None:
        item = self.db.scalar(
            select(AgentGoal).where(
                AgentGoal.id == goal_id,
                AgentGoal.workspace_id == workspace_id,
            )
        )
        return self._record(item) if item else None


class SQLAlchemyKnowledgeAdapter:
    """Adapter around the existing SQLite/PostgreSQL RAG persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def ingest(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        source: str,
        content: str,
        metadata: dict[str, Any],
    ) -> KnowledgeIngestResult:
        chunks = rag_ingest(
            self.db,
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            source=source,
            content=content,
            metadata=metadata,
        )
        return KnowledgeIngestResult(
            ids=[item.id for item in chunks],
            models=sorted({item.embedding_model for item in chunks}),
            providers=sorted({item.embedding_provider for item in chunks}),
        )

    def search(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        return rag_search(
            self.db,
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            query=query,
            top_k=top_k,
        )


class OllamaLanguageModelAdapter:
    """Adapter pattern: hides the provider-specific Ollama client behind a stable port."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or LLMClient()

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            return self.client.chat(messages)
        except ProviderModelUnavailable as error:
            raise ApplicationModelUnavailable(str(error)) from error


class SQLAlchemyUnitOfWork:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


EventHandler = Callable[[DomainEvent], None]


class LocalEventBus:
    """In-process event bus using Observer/Pub-Sub without extra RAM-heavy infrastructure."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event: DomainEvent) -> None:
        handlers = [*self._handlers.get(event.name, []), *self._handlers.get("*", [])]
        for handler in handlers:
            handler(event)


class AuditEventHandler:
    """Observer that maps AgentOS domain events onto the existing audit hash-chain."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def __call__(self, event: DomainEvent) -> None:
        details = dict(event.payload)
        details.setdefault("occurred_at", event.occurred_at.isoformat())
        record(
            self.db,
            workspace_id=event.workspace_id,
            project_id=event.project_id,
            task_id=event.task_id,
            actor=event.actor,
            action=event.name,
            outcome=event.outcome,
            details=details,
        )
