from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Project

from .db import get_rag_engine
from .ingestion import RagIndexer
from .jobs import claim_next_job, complete_job, fail_job, update_progress
from .runtime import get_rag_embedder, reload_rag_service


def process_one_rag_job(db: Session) -> bool:
    rag_engine = get_rag_engine()
    if rag_engine.dialect.name != "postgresql":
        return False
    job = claim_next_job(rag_engine)
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

        rag = reload_rag_service()
        indexer = RagIndexer(
            rag_engine,
            embedder,
            chunk_size=rag.settings.chunk_size_tokens,
            overlap=rag.settings.chunk_overlap_tokens,
        )
        result = indexer.index_project(
            project,
            progress=lambda done, total: update_progress(
                rag_engine, job["id"], done=done, total=total
            ),
        )
        rag.invalidate_project(
            organization_id=project.organization_id,
            project_id=project.id,
        )
        if int(result.get("failed") or 0) > 0:
            examples = result.get("errors") or []
            detail = f"{result['failed']} de {result['total']} arquivo(s) falharam na indexação"
            if examples:
                detail += ": " + " | ".join(str(item) for item in examples[:3])
            fail_job(rag_engine, job["id"], detail, result=result)
        else:
            complete_job(rag_engine, job["id"], result=result)
    except Exception as error:
        fail_job(rag_engine, job["id"], str(error))
    return True
