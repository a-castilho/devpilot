from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.container import build_agentos_services
from app.db import get_db
from app.models import Project, Workspace
from app.security import require_access


router = APIRouter(prefix="/api/agentos", dependencies=[Depends(require_access)])


class RepositoryIndexRequest(BaseModel):
    refresh: bool = False


class RepositorySearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=20_000)
    top_k: int = Field(default=5, ge=1, le=8)


class ImpactRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    depth: int = Field(default=2, ge=1, le=4)
    refresh: bool = False


class ExtensionToggleRequest(BaseModel):
    enabled: bool = True


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if item is None:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def _project(db: Session, workspace_id: str, project_id: str) -> Project:
    item = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if item is None:
        raise HTTPException(404, "Project not found")
    return item


@router.get("/intelligence/{project_id}")
def intelligence_status(project_id: str, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project(db, ws.id, project_id)
    record = build_agentos_services(db).intelligence.status(
        workspace_id=ws.id,
        project_id=project_id,
    )
    return None if record is None else asdict(record)


@router.post("/intelligence/{project_id}/index")
def index_repository(
    project_id: str,
    payload: RepositoryIndexRequest,
    db: Session = Depends(get_db),
):
    ws = _workspace(db)
    _project(db, ws.id, project_id)
    try:
        return build_agentos_services(db).intelligence.index_project(
            workspace_id=ws.id,
            project_id=project_id,
            refresh=payload.refresh,
        )
    except (LookupError, RuntimeError) as error:
        raise HTTPException(409, str(error)) from error


@router.post("/intelligence/{project_id}/search")
def search_repository(
    project_id: str,
    payload: RepositorySearchRequest,
    db: Session = Depends(get_db),
):
    ws = _workspace(db)
    _project(db, ws.id, project_id)
    matches = build_agentos_services(db).intelligence.search(
        workspace_id=ws.id,
        project_id=project_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return {"query": payload.query, "matches": matches}


@router.post("/intelligence/{project_id}/impact")
def impact_repository(
    project_id: str,
    payload: ImpactRequest,
    db: Session = Depends(get_db),
):
    ws = _workspace(db)
    _project(db, ws.id, project_id)
    services = build_agentos_services(db)
    depth = min(payload.depth, services.kernel.budget.max_impact_depth)
    try:
        report = services.intelligence.impact(
            project_id=project_id,
            path=payload.path,
            depth=depth,
            refresh=payload.refresh,
        )
    except (LookupError, RuntimeError) as error:
        raise HTTPException(409, str(error)) from error
    return asdict(report)


@router.get("/marketplace")
def marketplace_catalog():
    from app.agentos.application.extensions import ExtensionMarketplaceService

    return ExtensionMarketplaceService.catalog()


@router.get("/marketplace/activations")
def marketplace_activations(
    project_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    ws = _workspace(db)
    if project_id is not None:
        _project(db, ws.id, project_id)
    return build_agentos_services(db).marketplace.list_activations(
        workspace_id=ws.id,
        project_id=project_id,
    )


@router.post("/marketplace/{project_id}/{extension_key}")
def toggle_extension(
    project_id: str,
    extension_key: str,
    payload: ExtensionToggleRequest,
    db: Session = Depends(get_db),
):
    ws = _workspace(db)
    _project(db, ws.id, project_id)
    try:
        return build_agentos_services(db).marketplace.set_enabled(
            workspace_id=ws.id,
            project_id=project_id,
            extension_key=extension_key,
            enabled=payload.enabled,
        )
    except ValueError as error:
        raise HTTPException(404, str(error)) from error
