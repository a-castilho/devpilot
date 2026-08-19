from __future__ import annotations

from app.agentos.application.planning import PlanningStrategyFactory
from app.agentos.contracts import AgentPlan


def plan_goal(objective: str, *, mode: str = "resource-light") -> AgentPlan:
    """Compatibility facade for callers that predate the application-layer refactor.

    New code should depend on ``PlannerPort``/``GoalService``. Keeping this facade means MCP,
    tests and existing integrations can migrate incrementally without violating the dependency
    rule inside new use cases.
    """

    return PlanningStrategyFactory.create(mode).plan(objective)
