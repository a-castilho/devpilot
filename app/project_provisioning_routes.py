from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Organization, Project, ProviderCredential, Repository, Workspace
from app.security import require_access, require_super_admin
from app.services.audit import record
from app.services.cloud_provisioning import CloudConnection, provision_cloud_stack
from app.services.github_provisioning import GitHubProvisioningError, create_github_repository
from app.services.vault import Vault


AUTHORIZED_ORGANIZATION = "a-castilho"
CLOUD_PROVIDERS = ("neon", "render", "vercel")
CLOUD_CREDENTIAL_LABEL = "Principal"
router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


class ProjectProvisionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    description: str = Field(default="", max_length=10_000)
    agents_md: str = Field(default="", max_length=100_000)
    codex_config: dict = Field(default_factory=dict)
    provision_cloud: bool = True


class ProjectDeferredCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,99}$")
    description: str = Field(default="", max_length=10_000)
    agents_md: str = Field(default="", max_length=100_000)
    codex_config: dict = Field(default_factory=dict)
    organization_id: str | None = None
    default_branch: str = Field(default="main", pattern=r"^[A-Za-z0-9._/-]+$")


class CloudProviderConnect(BaseModel):
    token: str = Field(min_length=8, max_length=10_000)
    account_id: str = Field(default="", max_length=200)


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


def project_or_404(db: Session, workspace_id: str, project_id: str) -> Project:
    item = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        )
    )
    if not item:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return item


def _project_config(project: Project) -> dict[str, Any]:
    try:
        value = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def _cloud_credential(
    db: Session,
    workspace_id: str,
    provider: str,
) -> ProviderCredential | None:
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == f"cloud-{provider}",
            ProviderCredential.label == CLOUD_CREDENTIAL_LABEL,
        )
    )


def _cloud_connection_from_credential(credential: ProviderCredential) -> CloudConnection | None:
    if not credential.enabled:
        return None
    try:
        decrypted = Vault().decrypt(credential.encrypted_secret)
        payload = json.loads(decrypted)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    token = str(payload.get("token") or "")
    if not token:
        return None
    return CloudConnection(
        token=token,
        account_id=str(payload.get("account_id") or ""),
    )


def _cloud_connections(db: Session, workspace_id: str) -> dict[str, CloudConnection]:
    result: dict[str, CloudConnection] = {}
    for provider in CLOUD_PROVIDERS:
        credential = _cloud_credential(db, workspace_id, provider)
        if not credential:
            continue
        connection = _cloud_connection_from_credential(credential)
        if connection:
            result[provider] = connection
    return result


def _repository_full_name(db: Session, project: Project) -> str:
    repository = db.scalar(select(Repository).where(Repository.project_id == project.id))
    if repository and repository.full_name:
        return repository.full_name

    value = (project.repository_url or "").strip()
    value = value.removesuffix(".git")
    if "github.com/" in value:
        return value.split("github.com/", 1)[1].strip("/")
    if value.startswith("git@github.com:"):
        return value.split(":", 1)[1].strip("/")
    return value.strip("/")


def _cloud_status(project: Project) -> dict[str, Any]:
    config = _project_config(project)
    cloud = config.get("cloud")
    if isinstance(cloud, dict):
        return cloud
    return {
        "requested": [],
        "status": "not_requested",
        "providers": {},
        "missing_credentials": [],
        "errors": {},
    }


def _run_cloud_provisioning(
    db: Session,
    project: Project,
    *,
    actor: str,
) -> dict[str, Any]:
    config = _project_config(project)
    blueprint = config.get("project_blueprint")
    if not isinstance(blueprint, dict):
        blueprint = {}

    state = provision_cloud_stack(
        project_name=project.slug,
        repository_url=project.repository_url,
        repository_full_name=_repository_full_name(db, project),
        branch=project.default_branch or "main",
        blueprint=blueprint,
        connections=_cloud_connections(db, project.workspace_id),
        existing=config.get("cloud") if isinstance(config.get("cloud"), dict) else None,
    )
    config["cloud"] = state
    project.codex_config = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=actor,
        action="project.cloud_provision",
        outcome="success" if state["status"] == "provisioned" else state["status"],
        details={
            "status": state["status"],
            "requested": state["requested"],
            "providers": {
                provider: payload.get("status")
                for provider, payload in state["providers"].items()
            },
            "missing_credentials": state["missing_credentials"],
            "failed_providers": sorted(state["errors"]),
        },
    )
    db.commit()
    db.refresh(project)
    return state


@router.get("/cloud/providers")
def list_cloud_providers(
    db: Session = Depends(get_db),
    _: str = Depends(require_super_admin),
):
    ws = workspace(db)
    result = []
    for provider in CLOUD_PROVIDERS:
        credential = _cloud_credential(db, ws.id, provider)
        connection = _cloud_connection_from_credential(credential) if credential else None
        result.append(
            {
                "provider": provider,
                "configured": connection is not None,
                "enabled": bool(credential and credential.enabled),
                "account_id": connection.account_id if connection else "",
            }
        )
    return result


@router.put("/cloud/providers/{provider}")
def save_cloud_provider(
    provider: str,
    payload: CloudProviderConnect,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    provider = provider.strip().lower()
    if provider not in CLOUD_PROVIDERS:
        raise HTTPException(status_code=404, detail="Provedor cloud não suportado.")

    ws = workspace(db)
    item = _cloud_credential(db, ws.id, provider)
    if not item:
        item = ProviderCredential(
            workspace_id=ws.id,
            provider=f"cloud-{provider}",
            label=CLOUD_CREDENTIAL_LABEL,
            encrypted_secret="",
            models="[]",
        )
        db.add(item)

    secret = json.dumps(
        {"token": payload.token, "account_id": payload.account_id.strip()},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    item.encrypted_secret = Vault().encrypt(secret)
    item.enabled = True
    item.models = "[]"
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="cloud.provider_configured",
        details={
            "provider": provider,
            "has_account_id": bool(payload.account_id.strip()),
        },
    )
    db.commit()
    return {
        "provider": provider,
        "configured": True,
        "enabled": True,
        "account_id": payload.account_id.strip(),
    }


@router.get("/projects/{project_id}/cloud")
def project_cloud_status(
    project_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_super_admin),
):
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    return _cloud_status(project)


@router.post("/projects/{project_id}/cloud/provision")
def provision_existing_project_cloud(
    project_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    if not project.repository_url:
        raise HTTPException(status_code=409, detail="Conecte um repositório antes do provisionamento cloud.")
    return _run_cloud_provisioning(db, project, actor=actor)


@router.post("/projects/deferred", status_code=201)
def create_project_without_repository(
    payload: ProjectDeferredCreate,
    db: Session = Depends(get_db),
):
    """Create the DevPilot project now and allow the Git repository to be connected later."""
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
    actor: str = Depends(require_super_admin),
):
    """Create GitHub repository and optionally provision its managed cloud stack."""
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

    if payload.provision_cloud:
        _run_cloud_provisioning(db, item, actor=actor)

    return item
