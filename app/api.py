from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent, Project, ProviderCredential, Run, Task, TaskStatus, Workspace
from app.schemas import (
    ProjectCreate,
    ProjectUpdate,
    ProviderCreate,
    ProviderModelDiscovery,
    TaskCreate,
    VoiceCommand,
)
from app.security import require_access
from app.services.audit import record
from app.services.intent import interpret_voice
from app.services.policy import evaluate_task, validate_repository_url
from app.services.provider_models import (
    REFERENCE_CATALOG_DATE,
    SUPPORTED_MODEL_PROVIDERS,
    ProviderModelDiscoveryError,
    discover_provider_models,
    reference_provider_models,
)
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


def _stored_models(item: ProviderCredential) -> list[str]:
    try:
        values = json.loads(item.models or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def _model_payload(models) -> list[dict[str, str]]:
    return [model.to_dict() for model in models]


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
    return {"workspace": ws.name, "projects": projects, "tasks": tasks, "active": running, "completed": completed}


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    ws = workspace(db)
    return db.scalars(select(Project).where(Project.workspace_id == ws.id).order_by(Project.created_at.desc())).all()


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    ws = workspace(db)
    try:
        validate_repository_url(str(payload.repository_url))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    item = Project(
        workspace_id=ws.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        repository_url=str(payload.repository_url),
        default_branch=payload.default_branch,
        agents_md=payload.agents_md,
        codex_config=json.dumps(payload.codex_config),
    )
    db.add(item)
    db.flush()
    record(db, workspace_id=ws.id, project_id=item.id, actor="owner", action="project.created", details={"slug": item.slug, "repository": item.repository_url})
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


@router.get("/tasks/{task_id}/runs")
def task_runs(task_id: str, db: Session = Depends(get_db)):
    ws = workspace(db)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == ws.id))
    if not task:
        raise HTTPException(404, "Task not found")
    return db.scalars(
        select(Run).where(Run.task_id == task.id).order_by(Run.started_at.desc())
    ).all()


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
    return [{"id": item.id, "provider": item.provider, "label": item.label, "models": _stored_models(item), "enabled": item.enabled, "created_at": item.created_at} for item in items]


@router.get("/providers/model-catalog")
def provider_model_catalog(refresh: bool = True, db: Session = Depends(get_db)):
    """Return a useful model list immediately and refresh account-specific catalogs when possible.

    Without a saved credential, DevPilot serves a conservative public reference catalog so provider
    selection is never an empty UI. A saved or newly entered API key remains the source of truth for
    account-specific availability; live discovery replaces the reference list when it succeeds.
    """

    ws = workspace(db)
    credentials = db.scalars(
        select(ProviderCredential)
        .where(ProviderCredential.workspace_id == ws.id, ProviderCredential.enabled.is_(True))
        .order_by(ProviderCredential.created_at.desc())
    ).all()
    latest_by_provider: dict[str, ProviderCredential] = {}
    for credential in credentials:
        latest_by_provider.setdefault(credential.provider, credential)

    catalog: dict[str, dict] = {}
    changed = False
    for provider in sorted(SUPPORTED_MODEL_PROVIDERS):
        credential = latest_by_provider.get(provider)
        stored = _stored_models(credential) if credential else []
        reference = reference_provider_models(provider)
        entry = {
            "provider": provider,
            "source": "stored" if stored else "reference",
            "models": (
                [{"id": model_id, "label": model_id} for model_id in stored]
                if stored
                else _model_payload(reference)
            ),
            "connection_id": credential.id if credential else None,
            "reference_catalog_date": REFERENCE_CATALOG_DATE,
            "warning": "",
        }
        if refresh and credential:
            try:
                models = discover_provider_models(provider, Vault().decrypt(credential.encrypted_secret))
            except (ProviderModelDiscoveryError, ValueError) as error:
                entry["warning"] = str(error)
            else:
                model_ids = [model.id for model in models]
                credential.models = json.dumps(model_ids)
                entry.update(source="live", models=_model_payload(models), warning="")
                record(
                    db,
                    workspace_id=ws.id,
                    actor="owner",
                    action="provider.models_refreshed",
                    details={"provider": provider, "connection_id": credential.id, "count": len(models)},
                )
                changed = True
        catalog[provider] = entry

    catalog["custom"] = {
        "provider": "custom",
        "source": "manual",
        "models": [],
        "connection_id": None,
        "reference_catalog_date": REFERENCE_CATALOG_DATE,
        "warning": "Provedores customizados usam catálogo manual.",
    }
    if changed:
        db.commit()
    return {
        "refreshed_at": datetime.now(timezone.utc),
        "reference_catalog_date": REFERENCE_CATALOG_DATE,
        "providers": catalog,
    }


@router.post("/providers/discover-models")
def discover_models(payload: ProviderModelDiscovery, db: Session = Depends(get_db)):
    ws = workspace(db)
    try:
        models = discover_provider_models(payload.provider, payload.api_key)
    except ProviderModelDiscoveryError as error:
        record(
            db,
            workspace_id=ws.id,
            actor="owner",
            action="provider.models_discovery",
            outcome="failed",
            details={"provider": payload.provider},
        )
        db.commit()
        raise HTTPException(422, str(error)) from error
    record(
        db,
        workspace_id=ws.id,
        actor="owner",
        action="provider.models_discovery",
        details={"provider": payload.provider, "count": len(models)},
    )
    db.commit()
    return {
        "provider": payload.provider,
        "source": "live",
        "models": _model_payload(models),
        "refreshed_at": datetime.now(timezone.utc),
    }


@router.post("/providers", status_code=201)
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)):
    ws = workspace(db)
    models = [model.strip() for model in payload.models if model.strip()]

    if payload.provider in SUPPORTED_MODEL_PROVIDERS:
        try:
            discovered = discover_provider_models(payload.provider, payload.api_key)
        except ProviderModelDiscoveryError as error:
            raise HTTPException(422, str(error)) from error
        available = {model.id for model in discovered}
        if models:
            unavailable = sorted(set(models) - available)
            if unavailable:
                raise HTTPException(
                    422,
                    f"Modelos não disponíveis para esta chave: {', '.join(unavailable[:5])}",
                )
        else:
            models = [model.id for model in discovered]

    item = ProviderCredential(
        workspace_id=ws.id,
        provider=payload.provider,
        label=payload.label,
        encrypted_secret=Vault().encrypt(payload.api_key),
        models=json.dumps(models),
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        actor="owner",
        action="provider.created",
        details={"provider": item.provider, "label": item.label, "model_count": len(models)},
    )
    db.commit()
    return {"id": item.id, "provider": item.provider, "label": item.label, "models": models, "enabled": True}


@router.get("/audit")
def audit(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    ws = workspace(db)
    return db.scalars(select(AuditEvent).where(AuditEvent.workspace_id == ws.id).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
