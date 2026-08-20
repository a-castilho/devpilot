from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Organization, Project, ProviderCredential, Repository, Workspace
from app.security import require_access, require_super_admin
from app.services.audit import record
from app.services.github_provisioning import GitHubProvisioningError, create_github_repository
from app.services.vault import Vault


AUTHORIZED_ORGANIZATION = "a-castilho"
router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


class ProjectProvisionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    description: str = Field(default="", max_length=10_000)
    agents_md: str = Field(default="", max_length=100_000)
    codex_config: dict = Field(default_factory=dict)


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


@router.post("/projects/provision", status_code=201)
def provision_project(
    payload: ProjectProvisionCreate,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    """Authorize and create a private repository in a-castilho, then connect it as a DevPilot project."""
    ws = workspace(db)
    existing = db.scalar(
        select(Project).where(Project.workspace_id == ws.id, Project.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Project slug already exists: {payload.slug}")

    organization = authorized_organization(db, ws.id)
    access_token = organization_access_token(db, ws.id, organization)

    try:
        remote = create_github_repository(
            AUTHORIZED_ORGANIZATION,
            payload.slug,
            payload.description,
            access_token,
        )
    except GitHubProvisioningError as error:
        record(
            db,
            workspace_id=ws.id,
            actor=actor,
            action="project.repository_provision",
            outcome="failed",
            details={
                "organization_id": organization.id,
                "repository_name": payload.slug,
                "error": str(error),
            },
        )
        db.commit()
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error

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
        },
    )
    db.commit()
    db.refresh(item)
    return item
