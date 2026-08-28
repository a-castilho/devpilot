from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, Run, Task, TaskStatus, Workspace
from app.schemas import TaskCreate
from app.security import Principal, Role, require_access, require_roles
from app.services.audit import record
from app.services.bootstrap_admin_tasks import bootstrap_regulaai_radar_admin_task
from app.services.policy import evaluate_task


router = APIRouter(prefix="/api/ui", dependencies=[Depends(require_access)])

_GAME_MARKER = "[DEVPILOT_BUILD_GAME_V1]"
_GAME_METADATA_LABELS = ("PARTIDA", "FASE", "OBJETIVO")


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        raise HTTPException(503, "Workspace not initialized")
    return item


def _task_summary(row, *, project_name: str = "", pull_request_url: str = "") -> dict:
    return {
        "id": row.id,
        "project_id": row.project_id,
        "project_name": project_name,
        "title": row.title,
        "source": row.source,
        "status": row.status,
        "priority": row.priority,
        "requires_approval": row.requires_approval,
        "approved_at": row.approved_at,
        "pull_request_url": pull_request_url,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _game_prompt_metadata(prompt: str | None) -> str:
    lines = [_GAME_MARKER]
    wanted = {label: "" for label in _GAME_METADATA_LABELS}
    for raw_line in str(prompt or "").splitlines():
        line = raw_line.strip()
        for label in _GAME_METADATA_LABELS:
            prefix = f"{label}:"
            if not wanted[label] and line.startswith(prefix):
                wanted[label] = line
                break
    lines.extend(value for value in wanted.values() if value)
    return "\n".join(lines)


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
    return [_task_summary(row) for row in rows]


@router.get("/super-admin/tasks")
def super_admin_task_summaries(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(Role.SUPER_ADMIN)),
):
    """Return tasks owned by the current Super Admin, including latest PR link.

    Besides the normal persisted queue, the first access opportunistically imports
    known historical platform work. The bootstrap is idempotent and does nothing
    when the corresponding project is not provisioned yet.
    """
    bootstrap_regulaai_radar_admin_task(db.get_bind())
    db.expire_all()

    ws = _workspace(db)
    tasks = db.scalars(
        select(Task)
        .where(
            Task.workspace_id == ws.id,
            Task.owner_user_id == principal.user_id,
        )
        .order_by(Task.updated_at.desc(), Task.created_at.desc())
        .limit(limit)
    ).all()

    project_ids = {task.project_id for task in tasks}
    projects = {}
    if project_ids:
        projects = {
            item.id: item.name
            for item in db.scalars(select(Project).where(Project.id.in_(project_ids))).all()
        }

    output = []
    for task in tasks:
        latest_run = db.scalar(
            select(Run)
            .where(Run.task_id == task.id)
            .order_by(Run.attempt.desc(), Run.started_at.desc())
            .limit(1)
        )
        output.append(
            _task_summary(
                task,
                project_name=projects.get(task.project_id, ""),
                pull_request_url=(latest_run.pull_request_url if latest_run else ""),
            )
        )
    return output


@router.post("/super-admin/tasks", status_code=201)
def create_super_admin_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(Role.SUPER_ADMIN)),
):
    """Create an auditable task explicitly owned by the current Super Admin."""
    ws = _workspace(db)
    project = db.scalar(
        select(Project).where(
            Project.id == payload.project_id,
            Project.workspace_id == ws.id,
        )
    )
    if not project:
        raise HTTPException(404, "Project not found")

    decision = evaluate_task(payload.prompt, payload.requires_approval)
    item = Task(
        workspace_id=ws.id,
        owner_user_id=principal.user_id,
        project_id=payload.project_id,
        title=payload.title,
        prompt=payload.prompt,
        source=payload.source,
        priority=payload.priority,
        requires_approval=decision.requires_approval,
        status=(TaskStatus.awaiting_approval if decision.requires_approval else TaskStatus.queued),
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        project_id=item.project_id,
        task_id=item.id,
        actor=principal.actor,
        action="super_admin.task_created",
        details={"source": item.source, "approval_reasons": decision.reasons},
    )
    db.commit()
    db.refresh(item)
    return _task_summary(item, project_name=project.name)


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


@router.get("/game-tasks")
def game_task_summaries(
    project_id: str,
    limit: int = Query(24, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Compact game history for constrained browsers.

    The normal Task model carries the full execution prompt, which can be several
    kilobytes per phase. The game only needs its marker and three metadata lines
    to reconstruct progression, so this endpoint avoids serializing unrelated
    tasks and strips the large mission body before it reaches the browser.
    """
    ws = _workspace(db)
    rows = db.execute(
        select(
            Task.id,
            Task.project_id,
            Task.title,
            Task.prompt,
            Task.status,
            Task.created_at,
        )
        .where(
            Task.workspace_id == ws.id,
            Task.project_id == project_id,
            Task.title.like("[Jogo]%"),
        )
        .order_by(Task.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "project_id": row.project_id,
            "title": row.title,
            "prompt": _game_prompt_metadata(row.prompt),
            "status": row.status,
            "created_at": row.created_at,
        }
        for row in rows
    ]
