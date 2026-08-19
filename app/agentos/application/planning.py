from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Protocol

from app.agentos.catalog import AGENT_CATALOG
from app.agentos.contracts import AgentDefinition, AgentPlan, AgentStep


class PlanningStrategy(Protocol):
    def plan(self, objective: str) -> AgentPlan: ...


class DeterministicPlanningStrategy:
    """Low-memory planning strategy with no model dependency.

    The catalog is injected so the planner can be tested or extended without changing the
    orchestration algorithm. A future LLM-assisted planner only needs to implement the same
    ``PlanningStrategy`` protocol.
    """

    def __init__(
        self,
        catalog: Mapping[str, AgentDefinition],
        *,
        mode: str = "resource-light",
    ) -> None:
        self.catalog = catalog
        self.mode = mode

    @staticmethod
    def _keywords(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9_-]+", text.lower()))

    def _step(
        self,
        step_id: str,
        agent: str,
        title: str,
        objective: str,
        *,
        depends_on: list[str] | None = None,
        approval_required: bool = False,
    ) -> AgentStep:
        definition = self.catalog[agent]
        return AgentStep(
            id=step_id,
            agent=agent,
            title=title,
            objective=objective,
            depends_on=depends_on or [],
            tools=definition.default_tools,
            approval_required=approval_required,
        )

    def plan(self, objective: str) -> AgentPlan:
        words = self._keywords(objective)
        steps: list[AgentStep] = [
            self._step(
                "plan",
                "planner",
                "Decompose objective",
                "Clarify deliverables, constraints, acceptance criteria and execution order.",
            )
        ]

        research_words = {
            "rag",
            "regulation",
            "regulatory",
            "document",
            "documents",
            "knowledge",
            "research",
            "embeddings",
        }
        if words & research_words:
            steps.append(
                self._step(
                    "research",
                    "researcher",
                    "Retrieve context",
                    "Collect the minimum project and knowledge-base context needed for the work.",
                    depends_on=["plan"],
                )
            )
            architecture_dep = ["research"]
        else:
            architecture_dep = ["plan"]

        steps.append(
            self._step(
                "architecture",
                "architect",
                "Define solution boundaries",
                "Specify contracts, data flow, failure modes, security controls and resource limits.",
                depends_on=architecture_dep,
            )
        )

        implementation_ids: list[str] = []
        backend_words = {
            "api",
            "backend",
            "database",
            "db",
            "fastapi",
            "agent",
            "mcp",
            "rag",
            "llm",
            "service",
        }
        frontend_words = {"ui", "frontend", "dashboard", "pwa", "screen", "tela", "interface"}

        if words & backend_words or not words & frontend_words:
            steps.append(
                self._step(
                    "backend",
                    "backend",
                    "Implement backend slice",
                    "Implement the smallest production-shaped backend slice for the objective.",
                    depends_on=["architecture"],
                )
            )
            implementation_ids.append("backend")

        if words & frontend_words:
            steps.append(
                self._step(
                    "frontend",
                    "frontend",
                    "Implement client slice",
                    "Implement the dashboard/client changes against the agreed API contracts.",
                    depends_on=["architecture"],
                )
            )
            implementation_ids.append("frontend")

        if not implementation_ids:
            implementation_ids.append("architecture")

        steps.append(
            self._step(
                "review",
                "reviewer",
                "Review implementation",
                "Review correctness, security, maintainability and resource usage.",
                depends_on=implementation_ids,
            )
        )
        steps.append(
            self._step(
                "qa",
                "qa",
                "Verify acceptance criteria",
                "Run focused tests and produce evidence for each acceptance criterion.",
                depends_on=["review"],
            )
        )

        deploy_words = {"deploy", "release", "production", "docker", "ci", "cd"}
        if words & deploy_words:
            steps.append(
                self._step(
                    "delivery",
                    "devops",
                    "Prepare controlled delivery",
                    "Prepare build/deploy actions with rollback and explicit human approval.",
                    depends_on=["qa"],
                    approval_required=True,
                )
            )

        return AgentPlan(objective=objective, mode=self.mode, steps=steps)


class PlanningStrategyFactory:
    """Factory/registry for planning strategies (Factory + Strategy patterns)."""

    _builders: dict[str, Callable[[], PlanningStrategy]] = {
        "resource-light": lambda: DeterministicPlanningStrategy(
            AGENT_CATALOG, mode="resource-light"
        ),
        "standard": lambda: DeterministicPlanningStrategy(AGENT_CATALOG, mode="standard"),
    }

    @classmethod
    def register(cls, mode: str, builder: Callable[[], PlanningStrategy]) -> None:
        cls._builders[mode] = builder

    @classmethod
    def create(cls, mode: str = "resource-light") -> PlanningStrategy:
        try:
            return cls._builders[mode]()
        except KeyError as error:
            raise ValueError(f"Unknown planning mode: {mode}") from error
