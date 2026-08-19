from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

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


@dataclass(frozen=True, slots=True)
class AgentOSServices:
    goals: GoalService
    knowledge: KnowledgeService
    chat: ChatService


def build_agentos_services(db: Session) -> AgentOSServices:
    """Composition root for the AgentOS bounded context.

    This is the only place that wires application ports to concrete infrastructure adapters.
    FastAPI routes consume use cases rather than constructing provider or persistence clients.
    """

    events = LocalEventBus()
    events.subscribe("*", AuditEventHandler(db))

    uow = SQLAlchemyUnitOfWork(db)
    goals = SQLAlchemyGoalRepository(db)
    knowledge = SQLAlchemyKnowledgeAdapter(db)
    planner = PlannerAdapter()
    model = OllamaLanguageModelAdapter()

    return AgentOSServices(
        goals=GoalService(planner=planner, goals=goals, events=events, uow=uow),
        knowledge=KnowledgeService(knowledge=knowledge, events=events, uow=uow),
        chat=ChatService(knowledge=knowledge, model=model, events=events, uow=uow),
    )
