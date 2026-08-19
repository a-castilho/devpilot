from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agentos.application.execution import GraphExecutionService
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


@dataclass(frozen=True, slots=True)
class AgentOSServices:
    goals: GoalService
    knowledge: KnowledgeService
    chat: ChatService
    executions: GraphExecutionService


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
        ),
    )
