from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.agentos.contracts import AgentPlan
from app.agentos.domain.events import DomainEvent


@dataclass(frozen=True, slots=True)
class GoalRecord:
    id: str
    workspace_id: str
    project_id: str | None
    title: str
    objective: str
    status: str
    plan: AgentPlan
    created_at: datetime


@dataclass(frozen=True, slots=True)
class KnowledgeIngestResult:
    ids: list[str]
    models: list[str]
    providers: list[str]

    @property
    def chunks(self) -> int:
        return len(self.ids)


class PlannerPort(Protocol):
    def plan(self, objective: str, *, mode: str = "resource-light") -> AgentPlan: ...


class GoalRepositoryPort(Protocol):
    def add(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        title: str,
        objective: str,
        plan: AgentPlan,
    ) -> GoalRecord: ...

    def get(self, *, workspace_id: str, goal_id: str) -> GoalRecord | None: ...


class KnowledgePort(Protocol):
    def ingest(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        source: str,
        content: str,
        metadata: dict[str, Any],
    ) -> KnowledgeIngestResult: ...

    def search(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]: ...


class LanguageModelPort(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...


class EventBusPort(Protocol):
    def publish(self, event: DomainEvent) -> None: ...


class UnitOfWorkPort(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...
