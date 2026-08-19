from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RiskLevel = Literal["read", "isolated-write", "controlled"]
MemoryScope = Literal["global", "project", "goal", "task"]


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    mode: str = "resource-light"
    max_active_agents: int = 1
    max_council_members: int = 5
    max_rag_matches: int = 8
    max_context_chars: int = 40_000
    max_repository_files: int = 400
    max_repository_file_chars: int = 100_000
    max_repository_total_chars: int = 2_000_000
    max_dependency_nodes: int = 1_500
    max_impact_depth: int = 4
    max_execution_seconds: int = 1_800
    parallel_execution: bool = False


@dataclass(frozen=True, slots=True)
class LayerDefinition:
    name: str
    responsibility: str


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    risk: RiskLevel
    allowed_agents: tuple[str, ...]
    approval_required: bool = False


PLATFORM_LAYERS: tuple[LayerDefinition, ...] = (
    LayerDefinition("kernel", "Resource budgets, safety policy and capability authorization."),
    LayerDefinition("runtime", "Persistent graph execution, state machine, retries and checkpoints."),
    LayerDefinition("memory_os", "Hierarchical global/project/goal/task memory over the knowledge port."),
    LayerDefinition("tool_hub", "Capability registry and per-agent tool authorization."),
    LayerDefinition("app_hub", "Projects exposed as installable/operable AgentOS applications."),
    LayerDefinition("interfaces", "FastAPI, MCP, dashboard and future voice/event adapters."),
)


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "agent.plan": ToolSpec(
        "agent.plan", "Create or inspect AgentOS plans.", "read", ("supervisor",),
    ),
    "audit.read": ToolSpec(
        "audit.read", "Read audit metadata.", "read", ("supervisor", "security"),
    ),
    "rag.search": ToolSpec(
        "rag.search", "Search scoped knowledge.", "read",
        ("planner", "researcher", "architect", "database", "security", "performance", "ux", "docs"),
    ),
    "project.read": ToolSpec(
        "project.read", "Read project metadata and instructions.", "read",
        ("planner", "researcher", "architect", "database", "security", "performance", "ux", "docs"),
    ),
    "repo.read": ToolSpec(
        "repo.read", "Read repository content in the isolated project workspace.", "read",
        ("backend", "frontend", "reviewer", "qa", "database", "security", "performance", "ux", "docs"),
    ),
    "repo.index": ToolSpec(
        "repo.index", "Index bounded repository code and documentation into project-scoped knowledge.",
        "read", ("researcher", "architect", "reviewer", "security", "performance", "docs"),
    ),
    "code.impact": ToolSpec(
        "code.impact", "Inspect local dependency and reverse-impact relationships before edits.",
        "read", ("architect", "backend", "frontend", "reviewer", "qa", "database", "security", "performance"),
    ),
    "repo.write": ToolSpec(
        "repo.write", "Write only to an isolated task branch; never push/merge/deploy.",
        "isolated-write", ("backend", "frontend", "database", "docs"),
    ),
    "tests.run": ToolSpec(
        "tests.run", "Run bounded project tests without shell strings.", "isolated-write",
        ("backend", "frontend", "qa", "database", "security", "performance"),
    ),
    "diff.read": ToolSpec(
        "diff.read", "Inspect generated diffs.", "read",
        ("reviewer", "security", "performance", "docs"),
    ),
    "tests.read": ToolSpec(
        "tests.read", "Inspect test evidence and logs.", "read",
        ("reviewer", "qa", "security", "performance"),
    ),
    "ci.read": ToolSpec(
        "ci.read", "Inspect CI/build state without mutating delivery targets.", "read",
        ("devops", "reviewer", "qa"),
    ),
    "deploy.plan": ToolSpec(
        "deploy.plan", "Prepare a deployment/rollback plan without executing deployment.",
        "controlled", ("devops",), approval_required=True,
    ),
}


def memory_namespace(
    scope: MemoryScope,
    *,
    project_id: str | None = None,
    goal_id: str | None = None,
    task_id: str | None = None,
) -> str:
    if scope == "global":
        return "memory/global"
    if scope == "project":
        if not project_id:
            raise ValueError("project_id is required for project memory")
        return f"memory/project/{project_id}"
    if scope == "goal":
        if not goal_id:
            raise ValueError("goal_id is required for goal memory")
        return f"memory/goal/{goal_id}"
    if not task_id:
        raise ValueError("task_id is required for task memory")
    return f"memory/task/{task_id}"
