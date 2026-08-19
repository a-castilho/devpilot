from datetime import datetime, timezone

from app.agentos.application.planning import PlanningStrategyFactory
from app.agentos.application.ports import GoalRecord
from app.agentos.application.services import GoalService
from app.agentos.domain.events import DomainEvent
from app.agentos.infrastructure.adapters import LocalEventBus


class FakePlanner:
    def plan(self, objective: str, *, mode: str = "resource-light"):
        return PlanningStrategyFactory.create(mode).plan(objective)


class FakeGoals:
    def __init__(self):
        self.items = {}

    def add(self, *, workspace_id, project_id, title, objective, plan):
        item = GoalRecord(
            id="goal-1",
            workspace_id=workspace_id,
            project_id=project_id,
            title=title,
            objective=objective,
            status="planned",
            plan=plan,
            created_at=datetime.now(timezone.utc),
        )
        self.items[item.id] = item
        return item

    def get(self, *, workspace_id, goal_id):
        item = self.items.get(goal_id)
        return item if item and item.workspace_id == workspace_id else None


class FakeEvents:
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)


class FakeUnitOfWork:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_goal_service_depends_on_ports_and_emits_domain_event():
    events = FakeEvents()
    uow = FakeUnitOfWork()
    service = GoalService(
        planner=FakePlanner(),
        goals=FakeGoals(),
        events=events,
        uow=uow,
    )

    result = service.plan_goal(
        workspace_id="ws-1",
        project_id="project-1",
        title="Implementar API",
        objective="Implement RAG API with tests",
    )

    assert result.id == "goal-1"
    assert uow.commits == 1
    assert uow.rollbacks == 0
    assert events.published[0].name == "agentos.goal_planned"
    assert events.published[0].payload["goal_id"] == "goal-1"


def test_local_event_bus_uses_observer_subscription():
    bus = LocalEventBus()
    received = []
    bus.subscribe("agentos.test", received.append)
    bus.subscribe("*", received.append)

    event = DomainEvent(name="agentos.test", workspace_id="ws-1", payload={"ok": True})
    bus.publish(event)

    assert received == [event, event]


def test_planning_strategy_factory_keeps_resource_light_default():
    strategy = PlanningStrategyFactory.create("resource-light")
    plan = strategy.plan("Create a backend API")

    assert plan.mode == "resource-light"
    assert any(step.agent == "architect" for step in plan.steps)
    assert any(step.agent == "backend" for step in plan.steps)
