from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent, Project, ProviderCredential, Run, Task, TaskStatus, Workspace
from app.schemas import ProjectCreate, ProjectUpdate, ProviderCreate, TaskCreate, VoiceCommand
from app.security import require_access
from app.services.audit import record
from app.services.bootstrap import bootstrap_title, build_bootstrap_prompt
from app.services.intent import interpret_voice
from app.services.policy import evaluate_task, validate_repository_url
from app.services.vault import Vault


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


def workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def project_or_404(db: Session, workspace_id: str, project_id: str) -> Project:
    item = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if not item:
        raise HTTPException(404, "Project not found")
    return item


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    ws = workspace(db)
    projects = db.scalar(select(func.count(Project.id)).where(Project.workspace_id == ws.id)) or 0
    tasks = db.scalar(select(func.count(Task.id)).where(Task.workspace_id == ws.id)) or 0
    running = db.scalar(
        select(func.count(Task.id)).where(
            Task.workspace_id == ws.id,
            Task.status.in_([TaskStatus.queued, TaskStatus.running, TaskStatus.review]),
        )
    ) or 0
    completed = db.scalar(
        select(func.count(Task.id)).where(Task.workspace_id == ws.id, Task.status == TaskStatus.completed)
    ) or 0
    from app.config import get_settings

    return {
        "workspace": ws.name,
        "projects": projects,
        "tasks": tasks,
        "active": running,
        "completed": completed,
        "execution_enabled": get_settings().execution_enabled,
    }


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    ws = workspace(db)
    return db.scalars(select(Project).where(Project.workspace_id == ws.id).order_by(Project.created_at.desc())).all()


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    ws = workspace(db)
    existing = db.scalar(
        select(Project.id).where(Project.workspace_id == ws.id, Project.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Já existe um projeto com o slug '{payload.slug}'")
    try:
        validate_repository_url(str(payload.repository_url))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    codex_config = dict(payload.codex_config)
    codex_config.update(
        auto_start=payload.auto_start,
        generate_agents_md=payload.generate_agents_md,
    )
    item = Project(
        workspace_id=ws.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        repository_url=str(payload.repository_url),
        default_branch=payload.default_branch,
        agents_md=payload.agents_md,
        codex_config=json.dumps(codex_config),
    )
    db.add(item)
    db.flush()
    record(db, workspace_id=ws.id, project_id=item.id, actor="owner", action="project.created", details={"slug": item.slug, "repository": item.repository_url})
    if payload.auto_start:
        bootstrap = Task(
            workspace_id=ws.id,
            project_id=item.id,
            title=bootstrap_title(item),
            prompt=build_bootstrap_prompt(
                item,
                generate_agents_md=payload.generate_agents_md,
            ),
            source="api",
            status=TaskStatus.queued,
            requires_approval=False,
            priority=80,
        )
        db.add(bootstrap)
        db.flush()
        record(
            db,
            workspace_id=ws.id,
            project_id=item.id,
            task_id=bootstrap.id,
            actor="system",
            action="project.bootstrap_queued",
            details={"generate_agents_md": payload.generate_agents_md},
        )
    db.commit()
    return item


@router.patch("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    ws = workspace(db)
    item = project_or_404(db, ws.id, project_id)
    values = payload.model_dump(exclude_unset=True)
    if "repository_url" in values:
        values["repository_url"] = str(values["repository_url"])
        try:
            validate_repository_url(values["repository_url"])
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    if "codex_config" in values:
        values["codex_config"] = json.dumps(values["codex_config"])
    for key, value in values.items():
        setattr(item, key, value)
    record(db, workspace_id=ws.id, project_id=item.id, actor="owner", action="project.configured", details={"fields": sorted(values)})
    db.commit()
    return item


@router.post("/projects/{project_id}/analyze", status_code=201)
def analyze_project(project_id: str, db: Session = Depends(get_db)):
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    item = Task(
        workspace_id=ws.id,
        project_id=project.id,
        title=f"Análise técnica de {project.name}",
        prompt=(
            "Faça uma auditoria somente leitura do projeto. Identifique falhas funcionais, "
            "segurança, arquitetura, testes, desempenho, experiência do desenvolvedor e "
            "oportunidades de produto. Não modifique arquivos. Produza achados priorizados "
            "com evidência, impacto, recomendação e esforço estimado."
        ),
        source="dashboard",
        status=TaskStatus.queued,
        requires_approval=False,
        priority=70,
    )
    db.add(item)
    db.flush()
    record(db, workspace_id=ws.id, project_id=project.id, task_id=item.id, actor="owner", action="project.analysis_requested", details={"mode": "read-only"})
    db.commit()
    return item


@router.get("/tasks")
def list_tasks(project_id: str | None = None, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    ws = workspace(db)
    query = select(Task).where(Task.workspace_id == ws.id)
    if project_id:
        query = query.where(Task.project_id == project_id)
    return db.scalars(query.order_by(Task.created_at.desc()).limit(limit)).all()


@router.post("/tasks", status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    ws = workspace(db)
    project_or_404(db, ws.id, payload.project_id)
    decision = evaluate_task(payload.prompt, payload.requires_approval)
    item = Task(
        workspace_id=ws.id,
        **payload.model_dump(exclude={"requires_approval"}),
        requires_approval=decision.requires_approval,
        status=TaskStatus.awaiting_approval if decision.requires_approval else TaskStatus.queued,
    )
    db.add(item)
    db.flush()
    record(db, workspace_id=ws.id, project_id=item.project_id, task_id=item.id, actor="owner", action="task.created", details={"source": item.source, "approval_reasons": decision.reasons})
    db.commit()
    return item


@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str, db: Session = Depends(get_db)):
    ws = workspace(db)
    item = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == ws.id))
    if not item:
        raise HTTPException(404, "Task not found")
    if item.status != TaskStatus.awaiting_approval:
        raise HTTPException(409, "Task is not awaiting approval")
    item.status = TaskStatus.queued
    item.approved_at = datetime.now(timezone.utc)
    record(db, workspace_id=ws.id, project_id=item.project_id, task_id=item.id, actor="owner", action="task.approved", details={})
    db.commit()
    return item


@router.post("/voice/commands", status_code=201)
def voice_command(payload: VoiceCommand, db: Session = Depends(get_db)):
    ws = workspace(db)
    intent = interpret_voice(payload.transcript)
    project = None
    if payload.project_id:
        project = project_or_404(db, ws.id, payload.project_id)
    elif intent["project_hint"]:
        project = db.scalar(select(Project).where(Project.workspace_id == ws.id, Project.slug == intent["project_hint"]))
    if not project:
        raise HTTPException(422, "Select or mention a valid project")
    task = Task(
        workspace_id=ws.id,
        project_id=project.id,
        title=intent["title"],
        prompt=intent["prompt"],
        source="voice",
        status=TaskStatus.awaiting_approval,
        requires_approval=True,
    )
    db.add(task)
    db.flush()
    record(db, workspace_id=ws.id, project_id=project.id, task_id=task.id, actor="voice-owner", action="voice.command_interpreted", details={"transcript": payload.transcript, "intent": intent})
    db.commit()
    return {"task": task, "intent": intent, "message": "Comando registrado. Revise e aprove antes da execução."}


@router.get("/providers")
def list_providers(db: Session = Depends(get_db)):
    ws = workspace(db)
    items = db.scalars(select(ProviderCredential).where(ProviderCredential.workspace_id == ws.id)).all()
    return [{"id": item.id, "provider": item.provider, "label": item.label, "models": json.loads(item.models), "enabled": item.enabled, "created_at": item.created_at} for item in items]


@router.post("/providers", status_code=201)
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)):
    ws = workspace(db)
    item = ProviderCredential(workspace_id=ws.id, provider=payload.provider, label=payload.label, encrypted_secret=Vault().encrypt(payload.api_key), models=json.dumps(payload.models))
    db.add(item)
    db.flush()
    record(db, workspace_id=ws.id, actor="owner", action="provider.created", details={"provider": item.provider, "label": item.label})
    db.commit()
    return {"id": item.id, "provider": item.provider, "label": item.label, "models": payload.models, "enabled": True}


@router.get("/audit")
def audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    ws = workspace(db)
    return db.scalars(select(AuditEvent).where(AuditEvent.workspace_id == ws.id).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
