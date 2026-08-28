from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine, get_db
from app.models import Project
from app.rag.admin import RagAdminService
from app.rag.ingestion import RagIndexer
from app.rag.runtime import get_rag_embedder, get_rag_service
from app.security import require_super_admin


router = APIRouter(
    prefix="/api/super-admin/rag",
    tags=["super-admin-rag"],
    dependencies=[Depends(require_super_admin)],
)


def _admin() -> RagAdminService:
    return RagAdminService(get_rag_service())


@router.get("/overview")
def overview() -> dict[str, Any]:
    return _admin().overview()


@router.get("/health")
def health() -> dict[str, Any]:
    return _admin().health()


@router.get("/settings")
def settings() -> dict[str, Any]:
    return _admin().settings()


@router.patch("/settings")
def update_settings(changes: dict[str, Any]) -> dict[str, Any]:
    try:
        return _admin().update_settings(changes)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/{project_id}/index")
def index_project(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.organization_id:
        raise HTTPException(status_code=409, detail="Project must belong to an organization")
    embedder = get_rag_embedder()
    if embedder is None:
        raise HTTPException(status_code=503, detail="RAG embedding provider is not configured")
    settings = get_settings()
    indexer = RagIndexer(
        engine,
        embedder,
        chunk_size=settings.rag_chunk_size_tokens,
        overlap=settings.rag_chunk_overlap_tokens,
    )
    result = indexer.index_project(project)
    get_rag_service().invalidate_project(
        organization_id=project.organization_id,
        project_id=project.id,
    )
    return {"status": "ok", **result}


@router.post("/projects/{project_id}/retrieve")
def retrieve_project(project_id: str, payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.organization_id:
        raise HTTPException(status_code=409, detail="Project must belong to an organization")
    query = str(payload.get("query") or "").strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is required")
    result = get_rag_service().retrieve(
        organization_id=project.organization_id,
        project_id=project.id,
        query=query,
    )
    return {
        "mode": result.mode.value,
        "cache_hit": result.cache_hit,
        "retrieval_time_ms": result.retrieval_time_ms,
        "chunks": [
            {
                "id": chunk.id,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "source_path": chunk.source_path,
                "content": chunk.content,
                "score": chunk.score,
                "metadata": chunk.metadata,
            }
            for chunk in result.chunks
        ],
    }


@router.delete("/cache/{organization_id}/{project_id}")
def clear_project_cache(organization_id: str, project_id: str) -> dict[str, Any]:
    rag = get_rag_service()
    rag.invalidate_project(organization_id=organization_id, project_id=project_id)
    return {"status": "ok", "organization_id": organization_id, "project_id": project_id}
