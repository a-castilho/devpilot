from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine
from app.models import Project

from .ingestion import RagIndexer
from .jobs import claim_next_job, complete_job, fail_job, update_progress
from .runtime import get_rag_embedder, get_rag_service


def process_one_rag_job(db: Session) -> bool:
    if engine.dialect.name != "postgresql":
        return False
    job = claim_next_job(engine)
    if not job:
        return False

    try:
        project = db.get(Project, job["project_id"])
        if not project:
            raise RuntimeError("Project not found for RAG job")
        if not project.organization_id or project.organization_id != job["organization_id"]:
            raise RuntimeError("RAG job project scope mismatch")
        embedder = get_rag_embedder()
        if embedder is None:
            raise RuntimeError("RAG embedding provider is not configured")

        settings = get_settings()
        indexer = RagIndexer(
            engine,
            embedder,
            chunk_size=settings.rag_chunk_size_tokens,
            overlap=settings.rag_chunk_overlap_tokens,
        )
        indexer.index_project(
            project,
            progress=lambda done, total: update_progress(
                engine, job["id"], done=done, total=total
            ),
        )
        get_rag_service().invalidate_project(
            organization_id=project.organization_id,
            project_id=project.id,
        )
        complete_job(engine, job["id"])
    except Exception as error:
        fail_job(engine, job["id"], str(error))
    return True
