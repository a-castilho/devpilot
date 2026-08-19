from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from sqlalchemy import select

import app.models  # noqa: F401
from app.agentos.catalog import AGENT_CATALOG
from app.agentos.orchestrator import plan_goal
from app.agentos.rag import search
from app.db import Base, SessionLocal, engine
from app.models import Workspace


mcp = MCPServer(
    "DevPilot AgentOS",
    version="1.1.0",
    instructions=(
        "Use these tools to inspect the AgentOS catalog, plan software goals and retrieve "
        "grounded project knowledge. Write/deploy actions remain behind DevPilot approvals."
    ),
)


def _workspace_id() -> str:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
        if not item:
            item = Workspace(name="DevPilot", slug="default")
            db.add(item)
            db.commit()
            db.refresh(item)
        return item.id


@mcp.tool()
def list_agents() -> list[dict[str, Any]]:
    """List the specialist agents available in DevPilot AgentOS."""
    return [definition.model_dump() for definition in AGENT_CATALOG.values()]


@mcp.tool()
def plan_software_goal(objective: str) -> dict[str, Any]:
    """Create a resource-light dependency graph for a software objective."""
    return plan_goal(objective).model_dump()


@mcp.tool()
def search_knowledge(
    query: str,
    namespace: str = "default",
    project_id: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search DevPilot's local RAG knowledge store."""
    safe_top_k = max(1, min(top_k, 20))
    workspace_id = _workspace_id()
    with SessionLocal() as db:
        return search(
            db,
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            query=query,
            top_k=safe_top_k,
        )


if __name__ == "__main__":
    mcp.run()
