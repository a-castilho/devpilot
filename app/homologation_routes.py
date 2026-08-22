from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project
from app.project_provisioning_routes import (
    ProjectProvisionCreate,
    _cloud_connections,
    _project_config,
    _repository_full_name,
    _run_cloud_provisioning,
    project_or_404,
    provision_project,
    workspace,
)
from app.security import Principal, Role, require_access, require_roles
from app.services.audit import record
from app.services.homologation import (
    HomologationError,
    trigger_vercel_homologation,
    verify_homologation,
)


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


def project_operator(
    principal: Principal = Depends(require_roles(Role.OWNER, Role.ADMIN)),
) -> str:
    """OWNER/ADMIN operate projects; SUPER_ADMIN is implicitly accepted by require_roles."""
    return principal.actor


def _save_config(db: Session, project: Project, config: dict[str, Any]) -> None:
    project.codex_config = json.dumps(
        config,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    db.commit()
    db.refresh(project)


def _cloud(project: Project) -> tuple[dict[str, Any], dict[str, Any]]:
    config = _project_config(project)
    cloud = config.get("cloud")
    if not isinstance(cloud, dict):
        cloud = {
            "requested": [],
            "status": "not_requested",
            "providers": {},
            "missing_credentials": [],
            "errors": {},
        }
        config["cloud"] = cloud
    return config, cloud


def _ensure_vercel_homologation(
    db: Session,
    project: Project,
    *,
    actor: str,
) -> dict[str, Any]:
    config, cloud = _cloud(project)
    providers = cloud.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        cloud["providers"] = providers

    vercel = providers.get("vercel")
    if not isinstance(vercel, dict) or vercel.get("status") != "provisioned":
        return cloud

    existing = vercel.get("homologation")
    if isinstance(existing, dict) and existing.get("deployment_id"):
        return cloud

    connection = _cloud_connections(db, project.workspace_id).get("vercel")
    if not connection:
        return cloud

    try:
        deployment = trigger_vercel_homologation(
            connection=connection,
            project_id=str(vercel.get("project_id") or ""),
            project_name=project.slug,
            repository_full_name=_repository_full_name(db, project),
            branch=project.default_branch or "main",
        )
    except HomologationError:
        cloud["homologation"] = {
            "status": "pending",
            "url": "",
            "reason": "vercel_deployment_failed",
        }
        record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            actor=actor,
            action="project.homologation_deploy",
            outcome="failed",
            details={"provider": "vercel"},
        )
        _save_config(db, project, config)
        return cloud

    vercel["homologation"] = deployment
    cloud["homologation"] = {
        "status": "deploying",
        "url": deployment.get("url", ""),
    }
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=actor,
        action="project.homologation_deploy",
        details={
            "provider": "vercel",
            "deployment_id": deployment["deployment_id"],
            "environment": deployment["environment"],
        },
    )
    _save_config(db, project, config)
    return cloud


def _project_payload(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "repository_url": project.repository_url,
        "default_branch": project.default_branch,
        "status": project.status,
    }


@router.post("/projects/homologation", status_code=201)
def create_project_homologation(
    payload: ProjectProvisionCreate,
    db: Session = Depends(get_db),
    actor: str = Depends(project_operator),
):
    """Create repository + starter + Neon/Render/Vercel and launch a Vercel preview."""
    requested = payload.model_copy(update={"provision_cloud": True})
    project = provision_project(requested, db=db, actor=actor)
    cloud = _ensure_vercel_homologation(db, project, actor=actor)
    return {
        "project": _project_payload(project),
        "homologation": cloud,
    }


@router.get("/projects/{project_id}/homologation")
def homologation_status(
    project_id: str,
    db: Session = Depends(get_db),
):
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    _, cloud = _cloud(project)
    return {
        "project": _project_payload(project),
        "homologation": cloud,
    }


@router.post("/projects/{project_id}/homologation/provision")
def provision_project_homologation(
    project_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(project_operator),
):
    """Resume managed cloud provisioning and ensure a Vercel preview exists."""
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    if not project.repository_url:
        raise HTTPException(
            status_code=409,
            detail="Conecte um repositório antes da homologação.",
        )

    _run_cloud_provisioning(db, project, actor=actor)
    cloud = _ensure_vercel_homologation(db, project, actor=actor)
    return {
        "project": _project_payload(project),
        "homologation": cloud,
    }


@router.post("/projects/{project_id}/homologation/verify")
def verify_project_homologation(
    project_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(project_operator),
):
    """Check Render health, Vercel frontend and Vercel -> Render proxy."""
    ws = workspace(db)
    project = project_or_404(db, ws.id, project_id)
    _ensure_vercel_homologation(db, project, actor=actor)
    # The deployment helper may have refreshed the project/config.
    config, cloud = _cloud(project)

    verification = verify_homologation(cloud)
    cloud["homologation"] = verification

    providers = cloud.get("providers")
    if isinstance(providers, dict):
        vercel = providers.get("vercel")
        if isinstance(vercel, dict):
            deployment = vercel.get("homologation")
            if isinstance(deployment, dict) and verification["status"] == "ready":
                deployment["status"] = "ready"

    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=actor,
        action="project.homologation_verified",
        outcome="success" if verification["status"] == "ready" else "pending",
        details={
            "status": verification["status"],
            "checks": [
                {
                    "name": check["name"],
                    "ok": check["ok"],
                    "status_code": check["status_code"],
                }
                for check in verification["checks"]
            ],
        },
    )
    _save_config(db, project, config)
    return verification
