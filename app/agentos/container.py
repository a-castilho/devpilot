from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agentos.application.execution import GraphExecutionService
from app.agentos.application.platform import (
    AppHubService,
    CouncilService,
    KernelService,
    MemoryOSService,
    RuntimeService,
    ToolHubService,
)
from app.agentos.application.services import ChatService, GoalService, KnowledgeService
from app.agentos.infrastructure.adapters import (
    AuditEventHandler,
    LocalEventBus,
    OllamaLanguageModelAdapter,
    PlannerAdapter,
    SQLAlchemyGoalRepository,
    SQLAlchemyKnowledgeAdapter,
    SQLAlchemyUnitOfWork,
)
from app.agentos.infrastructure.execution import (
    CompositeCommandRunner,
    SQLAlchemyExecutionRepository,
)
from app.agentos.infrastructure.platform import SQLAlchemyAppCatalog


@dataclass(frozen=True, slots=True)
class AgentOSServices:
    goals: GoalService
    knowledge: KnowledgeService
    chat: ChatService
    executions: GraphExecutionService
    kernel: KernelService
    runtime: RuntimeService
    memory: MemoryOSService
    tools: ToolHubService
    apps: AppHubService
    council: CouncilService


def build_agentos_services(db: Session) -> AgentOSServices:
    """Composition root for the AgentOS bounded context."""

    events = LocalEventBus()
    events.subscribe("*", AuditEventHandler(db))

    uow = SQLAlchemyUnitOfWork(db)
    goals = SQLAlchemyGoalRepository(db)
    executions = SQLAlchemyExecutionRepository(db)
    knowledge = SQLAlchemyKnowledgeAdapter(db)
    planner = PlannerAdapter()
    model = OllamaLanguageModelAdapter()
    runner = CompositeCommandRunner(db, model)
    kernel = KernelService()
    tools = ToolHubService()
    apps = AppHubService(SQLAlchemyAppCatalog(db))

    return AgentOSServices(
        goals=GoalService(planner=planner, goals=goals, events=events, uow=uow),
        knowledge=KnowledgeService(knowledge=knowledge, events=events, uow=uow),
        chat=ChatService(knowledge=knowledge, model=model, events=events, uow=uow),
        executions=GraphExecutionService(
            goals=goals,
            executions=executions,
            runner=runner,
            events=events,
            uow=uow,
            tool_policy=tools,
        ),
        kernel=kernel,
        runtime=RuntimeService(executions=executions, kernel=kernel),
        memory=MemoryOSService(knowledge=knowledge, kernel=kernel),
        tools=tools,
        apps=apps,
        council=CouncilService(
            knowledge=knowledge,
            model=model,
            kernel=kernel,
            events=events,
            uow=uow,
        ),
    )
