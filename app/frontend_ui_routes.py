from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
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
_MAX_VISUAL_IDENTITY_PROJECTS = 50
_MAX_PROJECT_LOGO_LENGTH = 160_000
_DEFAULT_PROJECT_ACCENT = "#2dd4a8"
_ALLOWED_LOGO_DATA_PREFIXES = (
    "data:image/png;base64,",
    "data:image/jpeg;base64,",
    "data:image/webp;base64,",
)


class ProjectVisualIdentityUpdate(BaseModel):
    logo: str = Field(default="", max_length=_MAX_PROJECT_LOGO_LENGTH)
    accent: str = Field(default=_DEFAULT_PROJECT_ACCENT, pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("logo")
    @classmethod
    def validate_logo(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        if normalized.startswith("https://") or normalized.startswith(_ALLOWED_LOGO_DATA_PREFIXES):
            return normalized
        raise ValueError("Use upload PNG/JPG/WebP ou URL HTTPS para o logo")


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


def _project_summary(row) -> dict:
    return {
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


def _codex_config(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _visual_identity(raw: str | None) -> dict:
    identity = _codex_config(raw).get("visual_identity")
    identity = identity if isinstance(identity, dict) else {}
    logo = str(identity.get("logo") or "")
    if len(logo) > _MAX_PROJECT_LOGO_LENGTH:
        logo = ""
    accent = str(identity.get("accent") or _DEFAULT_PROJECT_ACCENT)
    if len(accent) != 7 or not accent.startswith("#") or any(char not in "0123456789abcdefABCDEF" for char in accent[1:]):
        accent = _DEFAULT_PROJECT_ACCENT
    return {
        "logo": logo,
        "accent": accent,
        "updated_at": str(identity.get("updated_at") or ""),
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
    include_project_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Small project payload for navigation and selectors.

    Deliberately excludes agents_md and codex_config, both Text columns that can
    become large enough to stall the browser when every project is serialized
    immediately after login. ``include_project_id`` preserves a previously
    selected project even when it falls outside the first lightweight page.
    """
    ws = _workspace(db)
    project_columns = (
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
    rows = list(
        db.execute(
            select(*project_columns)
            .where(Project.workspace_id == ws.id)
            .order_by(Project.created_at.desc())
            .limit(limit)
        ).all()
    )
    if include_project_id and not any(
        str(row.id) == str(include_project_id) for row in rows
    ):
        selected = db.execute(
            select(*project_columns).where(
                Project.workspace_id == ws.id,
                Project.id == include_project_id,
            )
        ).first()
        if selected:
            rows.append(selected)
    return [_project_summary(row) for row in rows]


@router.get("/project-identities")
def project_visual_identities(
    ids: str = Query("", max_length=4_000),
    db: Session = Depends(get_db),
):
    """Return only visual identity for the bounded set visible in Projects.

    The heavy ``codex_config`` Text value is read server-side only for the explicit
    project IDs currently rendered, and is never sent to the browser.
    """
    ws = _workspace(db)
    project_ids = list(dict.fromkeys(value.strip() for value in ids.split(",") if value.strip()))
    if len(project_ids) > _MAX_VISUAL_IDENTITY_PROJECTS:
        raise HTTPException(422, f"No máximo {_MAX_VISUAL_IDENTITY_PROJECTS} projetos por consulta")
    if not project_ids:
        return []
    rows = db.execute(
        select(Project.id, Project.codex_config).where(
            Project.workspace_id == ws.id,
            Project.id.in_(project_ids),
        )
    ).all()
    return [
        {"project_id": row.id, **_visual_identity(row.codex_config)}
        for row in rows
    ]


@router.patch("/projects/{project_id}/visual-identity")
def update_project_visual_identity(
    project_id: str,
    payload: ProjectVisualIdentityUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(Role.OWNER, Role.ADMIN)),
):
    """Update only a project's visual identity while preserving current config."""
    ws = _workspace(db)
    item = db.scalar(
        select(Project)
        .where(Project.id == project_id, Project.workspace_id == ws.id)
        .with_for_update()
    )
    if not item:
        raise HTTPException(404, "Project not found")

    config = _codex_config(item.codex_config)
    identity = {
        "logo": payload.logo,
        "accent": payload.accent.lower(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    config["visual_identity"] = identity
    item.codex_config = json.dumps(config, ensure_ascii=False)
    record(
        db,
        workspace_id=ws.id,
        project_id=item.id,
        actor=principal.actor,
        action="project.visual_identity_updated",
        details={"has_logo": bool(identity["logo"]), "accent": identity["accent"]},
    )
    db.commit()
    return {"project_id": item.id, **identity}


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