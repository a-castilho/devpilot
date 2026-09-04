from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.models import Organization, Project, ProviderCredential, Repository, Task, TaskStatus, Workspace
from app.security import Principal, Role, require_access, require_super_admin, session_principal
from app.services.audit import record
from app.services.github_provisioning import GitHubProvisioningError, create_github_repository
from app.services.vault import Vault


AUTHORIZED_ORGANIZATION = "a-castilho"
GENERIC_PROJECT_CREATE_ERROR = "Não foi possível criar o projeto. A administração foi notificada."
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


class ProjectProvisionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    description: str = Field(default="", max_length=10_000)
    agents_md: str = Field(default="", max_length=100_000)
    codex_config: dict = Field(default_factory=dict)


class ProjectDeferredCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    description: str = Field(default="", max_length=10_000)
    agents_md: str = Field(default="", max_length=100_000)
    codex_config: dict = Field(default_factory=dict)
    organization_id: str | None = None
    default_branch: str = Field(default="main", pattern=r"^[A-Za-z0-9._/-]+$")


def workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def authorized_organization(db: Session, workspace_id: str) -> Organization:
    item = db.scalar(
        select(Organization).where(
            Organization.workspace_id == workspace_id,
            Organization.provider == "github",
            func.lower(Organization.external_login) == AUTHORIZED_ORGANIZATION,
        )
    )
    if not item:
        raise HTTPException(
            status_code=409,
            detail="A organização a-castilho ainda não está conectada ao DevPilot.",
        )
    return item


def organization_access_token(db: Session, workspace_id: str, organization: Organization) -> str:
    if not organization.credential_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "A organização a-castilho precisa de uma credencial GitHub autorizada para criar "
                "repositórios antes de usar esta opção."
            ),
        )
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == organization.credential_id,
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == "github",
            ProviderCredential.enabled.is_(True),
        )
    )
    if not credential:
        raise HTTPException(status_code=409, detail="A credencial GitHub da organização está desativada.")
    try:
        return Vault().decrypt(credential.encrypted_secret)
    except ValueError as error:
        raise HTTPException(status_code=409, detail="A credencial GitHub da organização não pôde ser lida.") from error


def optional_organization(db: Session, workspace_id: str, organization_id: str | None) -> Organization | None:
    if not organization_id:
        return None
    item = db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.workspace_id == workspace_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Organização não encontrada.")
    return item


def provisioning_client_error(principal: Principal, error: Exception) -> HTTPException:
    """Keep Git/provider details restricted to SUPER_ADMIN while preserving them in audit logs."""
    if principal.role is Role.SUPER_ADMIN:
        if isinstance(error, HTTPException):
            return error
        if isinstance(error, GitHubProvisioningError):
            return HTTPException(status_code=error.status_code, detail=str(error))
    return HTTPException(status_code=503, detail=GENERIC_PROJECT_CREATE_ERROR)


def project_config(project: Project) -> dict:
    raw = project.codex_config
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return dict(value) if isinstance(value, dict) else {}
    return {}


def repository_provision_state(project: Project) -> dict:
    config = project_config(project)
    repository_url = str(project.repository_url or "").strip()
    state = str(config.get("repository_provision_state") or ("ready" if repository_url else "pending"))
    return {
        "state": state,
        "pending": bool(config.get("repository_pending", not bool(repository_url))),
        "error": str(config.get("repository_provision_error") or "").strip(),
        "repository_url": repository_url,
        "default_branch": str(project.default_branch or "main"),
    }


def queue_repository_repair(db: Session, project: Project, *, actor: str, task_id: str | None = None) -> dict:
    """Mark a missing repository for an explicit reprovision attempt.

    This does not run GitHub I/O inside the request. The caller schedules the
    background repair after the transaction commits.
    """
    if str(project.repository_url or "").strip():
        return repository_provision_state(project)
    config = project_config(project)
    config["repository_pending"] = True
    config["repository_mode"] = "deferred"
    config["repository_provision_state"] = "queued"
    config["repository_provision_error"] = ""
    project.codex_config = json.dumps(config)
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        task_id=task_id,
        actor=actor,
        action="project.repository_repair_queued",
        outcome="queued",
        details={"task_id": task_id, "repository_name": project.slug},
    )
    db.flush()
    return repository_provision_state(project)


def persist_deferred_project(
    db: Session,
    *,
    ws: Workspace,
    name: str,
    slug: str,
    description: str,
    agents_md: str,
    codex_config: dict,
    organization: Organization | None,
    default_branch: str,
    actor: str,
    source: str,
) -> Project:
    config = dict(codex_config)
    config["repository_pending"] = True
    config["repository_mode"] = "deferred"
    config["repository_provision_state"] = (
        "queued" if source == "automatic_provision_queued" else "pending"
    )
    config["repository_provision_error"] = ""

    item = Project(
        workspace_id=ws.id,
        organization_id=organization.id if organization else None,
        name=name,
        slug=slug,
        description=description,
        repository_url="",
        default_branch=default_branch,
        agents_md=agents_md,
        codex_config=json.dumps(config),
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        project_id=item.id,
        actor=actor,
        action="project.created_without_repository",
        details={
            "slug": item.slug,
            "repository_pending": True,
            "repository_provision_state": config["repository_provision_state"],
            "organization_id": item.organization_id,
            "source": source,
        },
    )
    db.commit()
    db.refresh(item)
    return item


def provision_repository_in_background(
    project_id: str,
    workspace_id: str,
    actor: str,
) -> None:
    """Provision Git after registration so provider latency never blocks the form submit."""
    with SessionLocal() as db:
        project = db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.workspace_id == workspace_id,
            )
        )
        if not project or str(project.repository_url or "").strip():
            return

        organization: Organization | None = None
        try:
            organization = authorized_organization(db, workspace_id)
            access_token = organization_access_token(db, workspace_id, organization)
            remote = create_github_repository(
                AUTHORIZED_ORGANIZATION,
                project.slug,
                project.description,
                access_token,
            )
        except Exception as error:  # external provider failure must never unwind the registration response
            error_text = str(error.detail) if isinstance(error, HTTPException) else str(error)
            config = project_config(project)
            config["repository_pending"] = True
            config["repository_mode"] = "deferred"
            config["repository_provision_state"] = "failed"
            config["repository_provision_error"] = error_text[:2000]
            project.codex_config = json.dumps(config)
            record(
                db,
                workspace_id=workspace_id,
                project_id=project.id,
                actor=actor,
                action="project.repository_provision",
                outcome="failed",
                details={
                    "organization_id": organization.id if organization else None,
                    "repository_name": project.slug,
                    "error": error_text,
                    "background": True,
                },
            )
            db.commit()
            logger.warning(
                "Background repository provisioning failed for project %s: %s",
                project_id,
                error,
            )
            return

        project.organization_id = organization.id
        project.repository_url = remote["clone_url"]
        project.default_branch = remote["default_branch"]
        config = project_config(project)
        config["repository_pending"] = False
        config["repository_mode"] = "automatic"
        config["repository_provision_state"] = "ready"
        config["repository_provision_error"] = ""
        project.codex_config = json.dumps(config)

        repository = db.scalar(select(Repository).where(Repository.project_id == project.id))
        if not repository:
            db.add(
                Repository(
                    organization_id=organization.id,
                    project_id=project.id,
                    external_id=remote["external_id"],
                    name=remote["name"],
                    full_name=remote["full_name"],
                    description=remote["description"],
                    clone_url=remote["clone_url"],
                    default_branch=remote["default_branch"],
                    visibility=remote["visibility"],
                    archived=remote["archived"],
                )
            )

        record(
            db,
            workspace_id=workspace_id,
            project_id=project.id,
            actor=actor,
            action="project.repository_provisioned",
            details={
                "organization_id": organization.id,
                "repository": remote["full_name"],
                "visibility": remote["visibility"],
                "authorized": True,
                "credential_source": "super_admin_managed_organization",
                "background": True,
            },
        )
        db.commit()


def provision_repository_and_resume_task(
    project_id: str,
    workspace_id: str,
    task_id: str,
    actor: str,
) -> None:
    """Repair the missing repository first, then retry the exact failed task.

    A recovery task cannot repair an empty repository URL because the recovery
    agent itself needs a checkout. This wrapper therefore performs provider
    provisioning outside the agent and only requeues the original task after a
    concrete clone URL exists.
    """
    provision_repository_in_background(project_id, workspace_id, actor)
    with SessionLocal() as db:
        project = db.scalar(
            select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        )
        task = db.scalar(
            select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
        )
        if not project or not task:
            return
        provision = repository_provision_state(project)
        if not provision["repository_url"]:
            record(
                db,
                workspace_id=workspace_id,
                project_id=project.id,
                task_id=task.id,
                actor=actor,
                action="project.repository_repair",
                outcome="failed",
                details={"error": provision["error"], "state": provision["state"]},
            )
            db.commit()
            return
        if task.status in {TaskStatus.failed, TaskStatus.blocked}:
            previous_status = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
            task.status = TaskStatus.queued
            task.updated_at = datetime.now(timezone.utc)
            record(
                db,
                workspace_id=workspace_id,
                project_id=project.id,
                task_id=task.id,
                actor=actor,
                action="project.repository_repair_resumed_task",
                outcome="queued",
                details={
                    "previous_status": previous_status,
                    "repository_url_ready": True,
                    "default_branch": project.default_branch,
                },
            )
            db.commit()


@router.get("/projects/{project_id}/repository/provisioning")
def project_repository_provisioning(project_id: str, db: Session = Depends(get_db)):
    ws = workspace(db)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == ws.id))
    if not project:
        raise HTTPException(404, "Project not found")
    return repository_provision_state(project)


@router.post("/projects/{project_id}/repository/retry", status_code=202)
def retry_project_repository(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = workspace(db)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == ws.id))
    if not project:
        raise HTTPException(404, "Project not found")
    if str(project.repository_url or "").strip():
        return repository_provision_state(project)
    queue_repository_repair(db, project, actor=actor)
    db.commit()
    background_tasks.add_task(provision_repository_in_background, project.id, ws.id, actor)
    return repository_provision_state(project)


@router.post("/projects/deferred", status_code=201)
def create_project_without_repository(
    payload: ProjectDeferredCreate,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    """Super Admin escape hatch: create now and connect a Git repository later."""
    ws = workspace(db)
    existing = db.scalar(
        select(Project).where(Project.workspace_id == ws.id, Project.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Project slug already exists: {payload.slug}")

    organization = optional_organization(db, ws.id, payload.organization_id)
    return persist_deferred_project(
        db,
        ws=ws,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        agents_md=payload.agents_md,
        codex_config=payload.codex_config,
        organization=organization,
        default_branch=payload.default_branch,
        actor=actor,
        source="manual",
    )


@router.post("/projects/provision", status_code=201)
def provision_project(
    payload: ProjectProvisionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_access),
):
    """Persist first and provision Git only after the HTTP response is ready."""
    ws = workspace(db)
    existing = db.scalar(
        select(Project).where(Project.workspace_id == ws.id, Project.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Project slug already exists: {payload.slug}")

    item = persist_deferred_project(
        db,
        ws=ws,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        agents_md=payload.agents_md,
        codex_config=payload.codex_config,
        organization=None,
        default_branch="main",
        actor=actor,
        source="automatic_provision_queued",
    )
    background_tasks.add_task(
        provision_repository_in_background,
        item.id,
        ws.id,
        actor,
    )
    return item
