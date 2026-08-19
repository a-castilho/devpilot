from __future__ import annotations

import re

from app.agentos.catalog import AGENT_CATALOG
from app.agentos.contracts import AgentPlan, AgentStep


def _keywords(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_-]+", text.lower()))


def _step(
    step_id: str,
    agent: str,
    title: str,
    objective: str,
    *,
    depends_on: list[str] | None = None,
    approval_required: bool = False,
) -> AgentStep:
    definition = AGENT_CATALOG[agent]
    return AgentStep(
        id=step_id,
        agent=agent,
        title=title,
        objective=objective,
        depends_on=depends_on or [],
        tools=definition.default_tools,
        approval_required=approval_required,
    )


def plan_goal(objective: str) -> AgentPlan:
    """Build a deterministic low-memory task graph.

    The first version intentionally avoids using an LLM for planning so the control plane
    stays available even when no model is loaded. Model-assisted planning can be layered on
    top later without changing the message contract.
    """
    words = _keywords(objective)
    steps: list[AgentStep] = [
        _step(
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
            _step(
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
        _step(
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
            _step(
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
            _step(
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
        _step(
            "review",
            "reviewer",
            "Review implementation",
            "Review correctness, security, maintainability and resource usage.",
            depends_on=implementation_ids,
        )
    )
    steps.append(
        _step(
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
            _step(
                "delivery",
                "devops",
                "Prepare controlled delivery",
                "Prepare build/deploy actions with rollback and explicit human approval.",
                depends_on=["qa"],
                approval_required=True,
            )
        )

    return AgentPlan(objective=objective, mode="resource-light", steps=steps)
