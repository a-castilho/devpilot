from __future__ import annotations

from app.models import Project


def project_rag_scope(project: Project) -> str:
    """Return the stable tenant scope used by RAG.

    Organization is optional in DevPilot. When a project is not linked to one,
    its workspace becomes the isolation boundary instead of disabling RAG.
    Both identifiers are UUID-sized and the RAG schema stores this value as a
    generic 36-character scope without a foreign-key dependency.
    """
    return str(project.organization_id or project.workspace_id)
