from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Organization, Project, ProviderCredential, Repository, Workspace
from app.security import Principal, Role, require_access, require_super_admin, session_principal
from app.services.audit import record
from app.services.github_provisioning import GitHubProvisioningError, create_github_repository
from app.services.vault import Vault


AUTHORIZED_ORGANIZATION = "a-castilho"
GENERIC_PROJECT_CREATE_ERROR = "Não foi possível criar o projeto. A administração foi notificada."
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


@router.post("/projects/deferred", status_code=201)
def create_project_without_repository(
    payload: ProjectDeferredCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_super_admin),
):
    """Super Admin escape hatch: create now and connect a Git repository later."""
    ws = workspace(db)
    existing = db.scalar(
        select(Project).where(Project.workspace_id == ws.id, Project.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Project slug already exists: {payload.slug}")

    organization = optional_organization(db, ws.id, payload.organization_id)
    config = dict(payload.codex_config)
    config["repository_pending"] = True
    config["repository_mode"] = "deferred"

    item = Project(
        workspace_id=ws.id,
        organization_id=organization.id if organization else None,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        repository_url="",
        default_branch=payload.default_branch,
        agents_md=payload.agents_md,
        codex_config=json.dumps(config),
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        project_id=item.id,
        actor="owner",
        action="project.created_without_repository",
        details={
            "slug": item.slug,
            "repository_pending": True,
            "organization_id": item.organization_id,
        },
    )
    db.commit()
    db.refresh(item)
    return item


@router.post("/projects/provision", status_code=201)
def provision_project(
    payload: ProjectProvisionCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_access),
):
    """Create Git automatically with the centrally managed SUPER_ADMIN organization credential."""
    ws = workspace(db)
    existing = db.scalar(
        select(Project).where(Project.workspace_id == ws.id, Project.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Project slug already exists: {payload.slug}")

    organization: Organization | None = None
    try:
        organization = authorized_organization(db, ws.id)
        access_token = organization_access_token(db, ws.id, organization)
        remote = create_github_repository(
            AUTHORIZED_ORGANIZATION,
            payload.slug,
            payload.description,
            access_token,
        )
    except (HTTPException, GitHubProvisioningError) as error:
        record(
            db,
            workspace_id=ws.id,
            actor=actor,
            action="project.repository_provision",
            outcome="failed",
            details={
                "organization_id": organization.id if organization else None,
                "repository_name": payload.slug,
                "error": str(error.detail) if isinstance(error, HTTPException) else str(error),
            },
        )
        db.commit()
        raise provisioning_client_error(principal, error) from error

    item = Project(
        workspace_id=ws.id,
        organization_id=organization.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        repository_url=remote["clone_url"],
        default_branch=remote["default_branch"],
        agents_md=payload.agents_md,
        codex_config=json.dumps(payload.codex_config),
    )
    db.add(item)
    db.flush()

    repository = Repository(
        organization_id=organization.id,
        project_id=item.id,
        external_id=remote["external_id"],
        name=remote["name"],
        full_name=remote["full_name"],
        description=remote["description"],
        clone_url=remote["clone_url"],
        default_branch=remote["default_branch"],
        visibility=remote["visibility"],
        archived=remote["archived"],
    )
    db.add(repository)

    record(
        db,
        workspace_id=ws.id,
        project_id=item.id,
        actor=actor,
        action="project.repository_provisioned",
        details={
            "organization_id": organization.id,
            "repository": remote["full_name"],
            "visibility": remote["visibility"],
            "authorized": True,
            "credential_source": "super_admin_managed_organization",
        },
    )
    db.commit()
    db.refresh(item)
    return item
