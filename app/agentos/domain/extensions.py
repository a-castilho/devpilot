from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtensionSpec:
    key: str
    name: str
    description: str
    agents: tuple[str, ...]
    tools: tuple[str, ...]
    recommended_apps: tuple[str, ...] = ()
    version: int = 1


EXTENSION_CATALOG: dict[str, ExtensionSpec] = {
    "software-core": ExtensionSpec(
        key="software-core",
        name="Software Core",
        description="Planning, architecture, implementation, review and QA for normal software delivery.",
        agents=("planner", "researcher", "architect", "backend", "frontend", "reviewer", "qa"),
        tools=("rag.search", "project.read", "repo.index", "repo.read", "code.impact", "repo.write", "tests.run", "diff.read", "tests.read"),
        recommended_apps=("regulaai", "maquinadeleads", "telaviva"),
    ),
    "assurance": ExtensionSpec(
        key="assurance",
        name="Assurance Council",
        description="Database, security and performance specialists for higher-risk changes.",
        agents=("database", "security", "performance"),
        tools=("rag.search", "project.read", "repo.index", "repo.read", "code.impact", "diff.read", "tests.read", "tests.run"),
        recommended_apps=("regulaai", "maquinadeleads", "telaviva"),
    ),
    "product-experience": ExtensionSpec(
        key="product-experience",
        name="Product Experience",
        description="UX and documentation specialists for user journeys, accessibility and living documentation.",
        agents=("ux", "docs"),
        tools=("rag.search", "project.read", "repo.index", "repo.read", "diff.read", "repo.write"),
        recommended_apps=("maquinadeleads", "telaviva"),
    ),
    "operations": ExtensionSpec(
        key="operations",
        name="Operations",
        description="Controlled CI and deployment planning; execution remains human approval-gated.",
        agents=("devops", "supervisor"),
        tools=("ci.read", "deploy.plan", "audit.read"),
        recommended_apps=("regulaai", "maquinadeleads", "telaviva"),
    ),
}
