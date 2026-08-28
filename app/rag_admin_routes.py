from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.models import Project
from app.rag.admin import RagAdminService
from app.rag.jobs import enqueue_index_job, list_jobs, retry_job
from app.rag.metrics import RagMetricsService
from app.rag.runtime import get_rag_service
from app.security import Principal, require_super_admin, session_principal
from app.services.audit import record


router = APIRouter(
    prefix="/api/super-admin/rag",
    tags=["super-admin-rag"],
    dependencies=[Depends(require_super_admin)],
)


def _admin() -> RagAdminService:
    return RagAdminService(get_rag_service())


def _metrics() -> RagMetricsService:
    return RagMetricsService(engine)


@router.get("/overview")
def overview() -> dict[str, Any]:
    data = _admin().overview()
    data["metrics"] = _metrics().overview()
    return data


@router.get("/health")
def health() -> dict[str, Any]:
    data = _admin().health()
    data["metrics"] = _metrics().overview()
    return data


@router.get("/metrics")
def metrics() -> dict[str, Any]:
    return _metrics().overview()


@router.get("/projects/{project_id}/metrics")
def project_metrics(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.organization_id:
        raise HTTPException(status_code=409, detail="Project must belong to an organization")
    return _metrics().project(organization_id=project.organization_id, project_id=project.id)


@router.get("/settings")
def settings() -> dict[str, Any]:
    return _admin().settings()


@router.patch("/settings")
def update_settings(
    changes: dict[str, Any],
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
) -> dict[str, Any]:
    before = _admin().settings()
    try:
        updated = _admin().update_settings(changes)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record(
        db,
        workspace_id=str(principal.workspace_id),
        actor=principal.actor,
        action="rag.settings.updated",
        details={"changes": changes, "before": before, "after": updated},
    )
    db.commit()
    return updated


@router.post("/projects/{project_id}/index", status_code=202)
def index_project(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
) -> dict[str, Any]:
    project = db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.organization_id:
        raise HTTPException(status_code=409, detail="Project must belong to an organization")
    job = enqueue_index_job(
        engine,
        organization_id=project.organization_id,
        project_id=project.id,
    )
    record(
        db,
        workspace_id=str(principal.workspace_id),
        project_id=project.id,
        actor=principal.actor,
        action="rag.index.enqueued",
        outcome=str(job["status"]),
        details={"job_id": job["id"], "created": job["created"], "organization_id": project.organization_id},
    )
    db.commit()
    return {"status": job["status"], "job_id": job["id"], "created": job["created"]}


@router.get("/jobs")
def jobs(project_id: str | None = None, limit: int = Query(default=50, ge=1, le=100)) -> list[dict]:
    return list_jobs(engine, project_id=project_id, limit=limit)


@router.post("/jobs/{job_id}/retry")
def retry(
    job_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
) -> dict[str, Any]:
    job = retry_job(engine, job_id)
    if not job:
        raise HTTPException(status_code=409, detail="Job cannot be retried")
    record(
        db,
        workspace_id=str(principal.workspace_id),
        project_id=str(job.get("project_id") or "") or None,
        actor=principal.actor,
        action="rag.index.retry",
        details={"job_id": job_id, "attempts": job.get("attempts")},
    )
    db.commit()
    return job


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
def clear_project_cache(
    organization_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
) -> dict[str, Any]:
    rag = get_rag_service()
    rag.invalidate_project(organization_id=organization_id, project_id=project_id)
    record(
        db,
        workspace_id=str(principal.workspace_id),
        project_id=project_id,
        actor=principal.actor,
        action="rag.cache.cleared",
        details={"organization_id": organization_id},
    )
    db.commit()
    return {"status": "ok", "organization_id": organization_id, "project_id": project_id}
