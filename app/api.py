from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    AuditEvent,
    Organization,
    Project,
    ProjectStatus,
    ProviderCredential,
    Repository,
    Run,
    Task,
    TaskStatus,
    Workspace,
)
from app.schemas import (
    OrganizationCreate,
    OrganizationSync,
    OrganizationUpdate,
    ProjectCreate,
    ProjectUpdate,
    ProviderCreate,
    TaskCreate,
    VoiceCommand,
)
from app.security import require_access, require_super_admin
from app.services.audit import record
from app.services.git_reader import grep as git_grep
from app.services.git_reader import log as git_log
from app.services.git_reader import read_file as git_read_file
from app.services.git_reader import status as git_status
from app.services.intent import interpret_voice
from app.services.organizations import fetch_github_repositories, project_slug
from app.services.policy import evaluate_task, normalize_repository_url
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


def organization_or_404(db: Session, workspace_id: str, organization_id: str) -> Organization:
    item = db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.workspace_id == workspace_id,
        )
    )
    if not item:
        raise HTTPException(404, "Organization not found")
    return item


def organization_view(db: Session, item: Organization) -> dict:
    repository_count = db.scalar(
        select(func.count(Repository.id)).where(Repository.organization_id == item.id)
    ) or 0
    project_count = db.scalar(
        select(func.count(Project.id)).where(Project.organization_id == item.id)
    ) or 0
    return {
        "id": item.id,
        "provider": item.provider,
        "name": item.name,
        "slug": item.slug,
        "external_login": item.external_login,
        "sync_status": item.sync_status,
        "last_sync_error": item.last_sync_error,
        "last_synced_at": item.last_synced_at,
        "has_credentials": bool(item.credential_id),
        "repository_count": repository_count,
        "project_count": project_count,
        "created_at": item.created_at,
    }


def repository_view(item: Repository) -> dict:
    return {
        "id": item.id,
        "organization_id": item.organization_id,
        "project_id": item.project_id,
        "external_id": item.external_id,
        "name": item.name,
        "full_name": item.full_name,
        "description": item.description,
        "clone_url": item.clone_url,
        "default_branch": item.default_branch,
        "visibility": item.visibility,
        "archived": item.archived,
        "last_seen_at": item.last_seen_at,
    }


def set_organization_credential(
    db: Session,
    ws: Workspace,
    organization: Organization,
    access_token: str,
) -> ProviderCredential:
    credential = None
    if organization.credential_id:
        credential = db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.id == organization.credential_id,
                ProviderCredential.workspace_id == ws.id,
            )
        )
    if not credential:
        credential = ProviderCredential(
            workspace_id=ws.id,
            provider="github",
            label=f"GitHub org {organization.slug}",
            encrypted_secret="",
            models="[]",
        )
        db.add(credential)
        db.flush()
        organization.credential_id = credential.id
    credential.encrypted_secret = Vault().encrypt(access_token)
    credential.enabled = True
    return credential


def organization_access_token(db: Session, ws: Workspace, organization: Organization) -> str | None:
    if not organization.credential_id:
        return None
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == organization.credential_id,
            ProviderCredential.workspace_id == ws.id,
            ProviderCredential.provider == "github",
            ProviderCredential.enabled.is_(True),
        )
    )
    if not credential:
        return None
    return Vault().decrypt(credential.encrypted_secret)


def available_project_slug(existing: set[str], repository_name: str) -> str:
    base = project_slug(repository_name)
    candidate = base
    suffix = 2
    while candidate in existing:
        tail = f"-{suffix}"
        candidate = f"{base[: 100 - len(tail)]}{tail}"
        suffix += 1
    existing.add(candidate)
    return candidate


def git_error(error: Exception) -> HTTPException:
    if isinstance(error, ValueError):
        return HTTPException(422, str(error))
    return HTTPException(502, str(error) or "Unable to read repository")


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


@router.get("/organizations")
def list_organizations(
    db: Session = Depends(get_db),
    _: str = Depends(require_super_admin),
):
    ws = workspace(db)
    items = db.scalars(
        select(Organization)
        .where(Organization.workspace_id == ws.id)
        .order_by(Organization.created_at.desc())
    ).all()
    return [organization_view(db, item) for item in items]


@router.post("/organizations", status_code=201)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = workspace(db)
    existing = db.scalar(
        select(Organization).where(
            Organization.workspace_id == ws.id,
            Organization.provider == "github",
            Organization.slug == payload.slug,
        )
    )
    if existing:
        raise HTTPException(409, f"Organization slug already exists: {payload.slug}")
    item = Organization(
        workspace_id=ws.id,
        provider="github",
        name=payload.name,
        slug=payload.slug,
        external_login=payload.github_login,
    )
    db.add(item)
    db.flush()
    if payload.access_token:
        set_organization_credential(db, ws, item, payload.access_token)
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="organization.created",
        details={"organization_id": item.id, "provider": "github", "login": item.external_login},
    )
    db.commit()
    return organization_view(db, item)


@router.patch("/organizations/{organization_id}")
def update_organization(
    organization_id: str,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = workspace(db)
    item = organization_or_404(db, ws.id, organization_id)
    changed: list[str] = []
    if payload.name is not None:
        item.name = payload.name
        changed.append("name")
    if payload.access_token is not None:
        set_organization_credential(db, ws, item, payload.access_token)
        changed.append("credential")
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="organization.configured",
        details={"organization_id": item.id, "fields": changed},
    )
    db.commit()
    return organization_view(db, item)


@router.get("/organizations/{organization_id}/repositories")
def list_organization_repositories(
    organization_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_super_admin),
):
    ws = workspace(db)
    organization_or_404(db, ws.id, organization_id)
    items = db.scalars(
        select(Repository)
        .where(Repository.organization_id == organization_id)
        .order_by(Repository.full_name)
    ).all()
    return [repository_view(item) for item in items]


@router.post("/organizations/{organization_id}/sync")
def sync_organization(
    organization_id: str,
    payload: OrganizationSync,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = workspace(db)
    item = organization_or_404(db, ws.id, organization_id)
    item.sync_status = "syncing"
    item.last_sync_error = ""
    db.commit()

    try:
        token = organization_access_token(db, ws, item)
        remote_repositories = fetch_github_repositories(item.external_login, token)
    except (RuntimeError, ValueError) as error:
        item.sync_status = "failed"
        item.last_sync_error = str(error)[:2_000]
        record(
            db,
            workspace_id=ws.id,
            actor=actor,
            action="organization.sync",
            outcome="failed",
            details={"organization_id": item.id, "error": item.last_sync_error},
        )
        db.commit()
        raise HTTPException(502, item.last_sync_error) from error

    existing_slugs = set(
        db.scalars(select(Project.slug).where(Project.workspace_id == ws.id)).all()
    )
    created_repositories = 0
    imported_projects = 0
    linked_projects = 0
    seen_at = datetime.now(timezone.utc)

    for remote in remote_repositories:
        repository = db.scalar(
            select(Repository).where(
                Repository.organization_id == item.id,
                Repository.external_id == remote["external_id"],
            )
        )
        if not repository:
            repository = Repository(
                organization_id=item.id,
                external_id=remote["external_id"],
                name=remote["name"],
                full_name=remote["full_name"],
                clone_url=remote["clone_url"],
            )
            db.add(repository)
            created_repositories += 1

        repository.name = remote["name"]
        repository.full_name = remote["full_name"]
        repository.description = remote["description"]
        repository.clone_url = remote["clone_url"]
        repository.default_branch = remote["default_branch"]
        repository.visibility = remote["visibility"]
        repository.archived = remote["archived"]
        repository.last_seen_at = seen_at

        project = None
        if repository.project_id:
            project = db.scalar(
                select(Project).where(
                    Project.id == repository.project_id,
                    Project.workspace_id == ws.id,
                )
            )
        if not project:
            project = db.scalar(
                select(Project).where(
                    Project.workspace_id == ws.id,
                    Project.repository_url == remote["clone_url"],
                )
            )
            if project:
                linked_projects += 1

        if not project and payload.import_projects:
            project = Project(
                workspace_id=ws.id,
                organization_id=item.id,
                name=remote["name"],
                slug=available_project_slug(existing_slugs, remote["name"]),
                description=remote["description"],
                repository_url=remote["clone_url"],
                default_branch=remote["default_branch"],
                agents_md="",
                codex_config="{}",
                status=ProjectStatus.archived if remote["archived"] else ProjectStatus.active,
            )
            db.add(project)
            db.flush()
            imported_projects += 1

        if project:
            project.organization_id = item.id
            repository.project_id = project.id

    item.sync_status = "ready"
    item.last_sync_error = ""
    item.last_synced_at = seen_at
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="organization.sync",
        details={
            "organization_id": item.id,
            "repositories": len(remote_repositories),
            "created_repositories": created_repositories,
            "imported_projects": imported_projects,
            "linked_projects": linked_projects,
        },
    )
    db.commit()
    return {
        "organization": organization_view(db, item),
        "repositories": len(remote_repositories),
        "created_repositories": created_repositories,
        "imported_projects": imported_projects,
        "linked_projects": linked_projects,
    }


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    ws = workspace(db)
    return db.scalars(select(Project).where(Project.workspace_id == ws.id).order_by(Project.created_at.desc())).all()


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    ws = workspace(db)
    existing = db.scalar(
        select(Project).where(Project.workspace_id == ws.id, Project.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Project slug already exists: {payload.slug}")
    if payload.organization_id:
        organization_or_404(db, ws.id, payload.organization_id)
    try:
        repository_url = normalize_repository_url(payload.repository_url)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    item = Project(
        workspace_id=ws.id,
        organization_id=payload.organization_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        repository_url=repository_url,
        default_branch=payload.default_branch,
        agents_md=payload.agents_md,
        codex_config=json.dumps(payload.codex_config),
    )
    db.add(item)
    db.flush()
    record(db, workspace_id=ws.id, project_id=item.id, actor="owner", action="project.created", details={"slug": item.slug, "repository": item.repository_url, "organization_id": item.organization_id})
    db.commit()
    return item


@router.patch("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    ws = workspace(db)
    item = project_or_404(db, ws.id, project_id)
    values = payload.model_dump(exclude_unset=True)
    if "repository_url" in values:
        try:
            values["repository_url"] = normalize_repository_url(values["repository_url"])
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
    if values.get("organization_id"):
        organization_or_404(db, ws.id, values["organization_id"])
    if "codex_config" in values:
        values["codex_config"] = json.dumps(values["codex_config"])
    for key, value in values.items():
        setattr(item, key, value)
    record(db, workspace_id=ws.id, project_id=item.id, actor="owner", action="project.configured", details={"fields": sorted(values)})
    db.commit()
    return item


@router.get("/projects/{project_id}/git/status")
def project_git_status(project_id: str, db: Session = Depends(get_db)):
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    try:
        return git_status(project)
    except (ValueError, RuntimeError) as error:
        raise git_error(error) from error


@router.get("/projects/{project_id}/git/log")
def project_git_log(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
    ref: str | None = Query(default=None, max_length=180),
    db: Session = Depends(get_db),
):
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    try:
        return {
            "project_id": project.id,
            "ref": ref or f"origin/{project.default_branch}",
            "commits": git_log(project, limit=limit, ref=ref),
        }
    except (ValueError, RuntimeError) as error:
        raise git_error(error) from error


@router.get("/projects/{project_id}/git/search")
def project_git_search(
    project_id: str,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(100, ge=1, le=500),
    ref: str | None = Query(default=None, max_length=180),
    db: Session = Depends(get_db),
):
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    try:
        return {
            "project_id": project.id,
            "query": q,
            "ref": ref or f"origin/{project.default_branch}",
            "matches": git_grep(project, query=q, limit=limit, ref=ref),
        }
    except (ValueError, RuntimeError) as error:
        raise git_error(error) from error


@router.get("/projects/{project_id}/git/file")
def project_git_file(
    project_id: str,
    path: str = Query(min_length=1, max_length=500),
    ref: str | None = Query(default=None, max_length=180),
    db: Session = Depends(get_db),
):
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    try:
        return git_read_file(project, path=path, ref=ref)
    except (ValueError, RuntimeError) as error:
        raise git_error(error) from error


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
    decision = evaluate_task(intent["prompt"], False)
    task = Task(
        workspace_id=ws.id,
        project_id=project.id,
        title=intent["title"],
        prompt=intent["prompt"],
        source="voice",
        status=TaskStatus.awaiting_approval if decision.requires_approval else TaskStatus.queued,
        requires_approval=decision.requires_approval,
    )
    db.add(task)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        task_id=task.id,
        actor="voice-owner",
        action="voice.command_interpreted",
        details={
            "transcript": payload.transcript,
            "intent": intent,
            "approval_reasons": decision.reasons,
            "automatic": not decision.requires_approval,
        },
    )
    db.commit()
    message = (
        "Comando registrado e enfileirado para execução automática."
        if not decision.requires_approval
        else "Comando registrado. A política identificou uma ação de alto risco e exige aprovação."
    )
    return {"task": task, "intent": intent, "message": message}


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
