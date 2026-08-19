from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agentos.application.app_connections import KnownAppConnectionService
from app.agentos.application.execution import GraphExecutionService
from app.agentos.application.extensions import ExtensionMarketplaceService
from app.agentos.application.intelligence import RepositoryIntelligenceService
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
    ConfiguredLanguageModelAdapter,
    LocalEventBus,
    PlannerAdapter,
    SQLAlchemyGoalRepository,
    SQLAlchemyKnowledgeAdapter,
    SQLAlchemyUnitOfWork,
)
from app.agentos.infrastructure.execution import (
    CompositeCommandRunner,
    SQLAlchemyExecutionRepository,
)
from app.agentos.infrastructure.extensions import SQLAlchemyExtensionActivations
from app.agentos.infrastructure.intelligence import (
    LocalRepositorySnapshotAdapter,
    SQLAlchemyRepositoryIndex,
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
    app_connections: KnownAppConnectionService
    intelligence: RepositoryIntelligenceService
    marketplace: ExtensionMarketplaceService
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
    model = ConfiguredLanguageModelAdapter(db)
    runner = CompositeCommandRunner(db, model)
    kernel = KernelService()
    extension_activations = SQLAlchemyExtensionActivations(db)
    tools = ToolHubService(extension_activations)
    app_catalog = SQLAlchemyAppCatalog(db)
    apps = AppHubService(app_catalog)
    snapshots = LocalRepositorySnapshotAdapter(
        db,
        max_files=kernel.budget.max_repository_files,
        max_file_chars=kernel.budget.max_repository_file_chars,
        max_total_chars=kernel.budget.max_repository_total_chars,
    )

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
        memory=MemoryOSService(
            knowledge=knowledge,
            kernel=kernel,
            events=events,
            uow=uow,
        ),
        tools=tools,
        apps=apps,
        app_connections=KnownAppConnectionService(
            catalog=app_catalog,
            knowledge=knowledge,
            events=events,
            uow=uow,
        ),
        intelligence=RepositoryIntelligenceService(
            snapshots=snapshots,
            indexes=SQLAlchemyRepositoryIndex(db),
            knowledge=knowledge,
            events=events,
            uow=uow,
        ),
        marketplace=ExtensionMarketplaceService(
            activations=extension_activations,
            events=events,
            uow=uow,
        ),
        council=CouncilService(
            knowledge=knowledge,
            model=model,
            kernel=kernel,
            events=events,
            uow=uow,
        ),
    )
