from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.rag.admin import RagAdminService
from app.rag.runtime import get_rag_service
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


@router.delete("/cache/{organization_id}/{project_id}")
def clear_project_cache(organization_id: str, project_id: str) -> dict[str, Any]:
    rag = get_rag_service()
    rag.invalidate_project(organization_id=organization_id, project_id=project_id)
    return {"status": "ok", "organization_id": organization_id, "project_id": project_id}
