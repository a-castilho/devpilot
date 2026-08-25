from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, Task, Workspace
from app.security import require_access


router = APIRouter(prefix="/api/ui", dependencies=[Depends(require_access)])


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        raise HTTPException(503, "Workspace not initialized")
    return item


@router.get("/projects")
def project_summaries(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Small project payload for navigation and selectors.

    Deliberately excludes agents_md and codex_config, both Text columns that can
    become large enough to stall the browser when every project is serialized
    immediately after login.
    """
    ws = _workspace(db)
    rows = db.execute(
        select(
            Project.id,
            Project.organization_id,
            Project.name,
            Project.slug,
            Project.description,
            Project.repository_url,
            Project.default_branch,
            Project.status,
            Project.created_at,
        )
        .where(Project.workspace_id == ws.id)
        .order_by(Project.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "organization_id": row.organization_id,
            "name": row.name,
            "slug": row.slug,
            "description": row.description,
            "repository_url": row.repository_url,
            "default_branch": row.default_branch,
            "status": row.status,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/tasks")
def task_summaries(
    limit: int = Query(20, ge=1, le=50),
    project_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Small task payload; prompt is loaded only when the user asks for it."""
    ws = _workspace(db)
    query = select(
        Task.id,
        Task.project_id,
        Task.title,
        Task.source,
        Task.status,
        Task.priority,
        Task.requires_approval,
        Task.approved_at,
        Task.created_at,
        Task.updated_at,
    ).where(Task.workspace_id == ws.id)
    if project_id:
        query = query.where(Task.project_id == project_id)
    rows = db.execute(query.order_by(Task.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": row.id,
            "project_id": row.project_id,
            "title": row.title,
            "source": row.source,
            "status": row.status,
            "priority": row.priority,
            "requires_approval": row.requires_approval,
            "approved_at": row.approved_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.get("/tasks/{task_id}")
def task_detail(task_id: str, db: Session = Depends(get_db)):
    """Fetch the large prompt only for one task on explicit user action."""
    ws = _workspace(db)
    item = db.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == ws.id)
    )
    if not item:
        raise HTTPException(404, "Task not found")
    return {
        "id": item.id,
        "project_id": item.project_id,
        "title": item.title,
        "prompt": item.prompt,
        "source": item.source,
        "status": item.status,
        "priority": item.priority,
        "requires_approval": item.requires_approval,
        "approved_at": item.approved_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
