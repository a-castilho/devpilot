from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    id: str
    goal_id: str
    workspace_id: str
    project_id: str | None
    status: str
    idempotency_key: str
    current_step_id: str
    failure_reason: str
    checkpoint: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True, slots=True)
class StepExecutionRecord:
    id: str
    execution_id: str
    step_id: str
    agent: str
    title: str
    objective: str
    depends_on: list[str]
    tools: list[str]
    approval_required: bool
    approved_at: datetime | None
    status: str
    attempt: int
    max_attempts: int
    idempotency_key: str
    command: dict[str, Any]
    output: dict[str, Any]
    checkpoint: dict[str, Any]
    external_task_id: str | None
    error: str
    next_attempt_at: datetime | None


@dataclass(frozen=True, slots=True)
class AgentCommand:
    kind: str
    step_id: str
    agent: str
    title: str
    objective: str
    tools: list[str]
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CommandResult:
    status: str
    output: dict[str, Any] = field(default_factory=dict)
    checkpoint: dict[str, Any] = field(default_factory=dict)
    external_task_id: str | None = None


@dataclass(frozen=True, slots=True)
class AppRecord:
    id: str
    name: str
    slug: str
    description: str
    repository_url: str
    status: str


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


class ExecutionRepositoryPort(Protocol):
    def create(
        self,
        *,
        goal: GoalRecord,
        idempotency_key: str,
        max_attempts: int,
    ) -> ExecutionRecord: ...

    def get_by_idempotency(
        self, *, workspace_id: str, idempotency_key: str
    ) -> ExecutionRecord | None: ...

    def get(self, *, workspace_id: str, execution_id: str) -> ExecutionRecord | None: ...

    def next_active(self) -> ExecutionRecord | None: ...

    def steps(self, *, execution_id: str) -> list[StepExecutionRecord]: ...

    def set_execution(
        self,
        *,
        execution_id: str,
        status: str | None = None,
        current_step_id: str | None = None,
        failure_reason: str | None = None,
        checkpoint: dict[str, Any] | None = None,
        completed: bool = False,
    ) -> ExecutionRecord: ...

    def set_step(
        self,
        *,
        step_record_id: str,
        status: str | None = None,
        attempt: int | None = None,
        approved: bool = False,
        command: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
        checkpoint: dict[str, Any] | None = None,
        external_task_id: str | None = None,
        error: str | None = None,
        next_attempt_at: datetime | None = None,
        clear_next_attempt: bool = False,
        started: bool = False,
        finished: bool = False,
    ) -> StepExecutionRecord: ...


class CommandRunnerPort(Protocol):
    def run(self, command: AgentCommand, step: StepExecutionRecord) -> CommandResult: ...

    def poll(self, command: AgentCommand, step: StepExecutionRecord) -> CommandResult: ...

    def compensate(self, command: AgentCommand, step: StepExecutionRecord) -> dict[str, Any]: ...


class ToolPolicyPort(Protocol):
    def assert_allowed(
        self,
        *,
        agent: str,
        tools: list[str],
        approval_granted: bool,
        workspace_id: str | None = None,
        project_id: str | None = None,
    ) -> None: ...


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


class AppCatalogPort(Protocol):
    def list_apps(self, *, workspace_id: str) -> list[AppRecord]: ...


class LanguageModelPort(Protocol):
    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...


class EventBusPort(Protocol):
    def publish(self, event: DomainEvent) -> None: ...


class UnitOfWorkPort(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...
