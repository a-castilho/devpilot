from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Project
from app.security import Principal, Role, require_roles
from app.services.audit import record
from app.services.deployment_policy import deployment_risk, evaluate_deployment, normalize_environment
from app.services.host_actions import queue_host_action


router = APIRouter(prefix="/api/admin/deployments", tags=["admin-deployments"])
manage_deployments = require_roles(Role.SUPER_ADMIN)
_CONFIG_KEY = "manual_deploy"
_AUTH_KEY = "deployment_authorization"


class ManualDeployConfig(BaseModel):
    enabled: bool = False
    environment: str = Field(default="homolog", min_length=1, max_length=40)
    branch: str = Field(default="main", min_length=1, max_length=120)
    workdir: str = Field(default="", min_length=1, max_length=500)
    command: str = Field(default="", min_length=1, max_length=4000)
    timeout_seconds: int = Field(default=900, ge=30, le=3600)

    @field_validator("environment", "branch", "workdir", "command")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Campo obrigatório")
        if "\x00" in value:
            raise ValueError("Valor inválido")
        return value


class DeploymentAuthorizationInput(BaseModel):
    approved: bool = True
    note: str = Field(default="", max_length=500)


def _project(db: Session, principal: Principal, project_id: str) -> Project:
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == principal.workspace_id,
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project


def _root_config(project: Project) -> dict[str, Any]:
    try:
        value = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        value = {}
    return value if isinstance(value, dict) else {}


def _deploy_config(project: Project) -> dict[str, Any]:
    raw = _root_config(project).get(_CONFIG_KEY)
    if not isinstance(raw, dict):
        return {
            "enabled": False,
            "environment": "homolog",
            "branch": project.default_branch or "main",
            "workdir": "",
            "command": "",
            "timeout_seconds": 900,
        }
    return {
        "enabled": bool(raw.get("enabled", False)),
        "environment": str(raw.get("environment") or "homolog"),
        "branch": str(raw.get("branch") or project.default_branch or "main"),
        "workdir": str(raw.get("workdir") or ""),
        "command": str(raw.get("command") or ""),
        "timeout_seconds": int(raw.get("timeout_seconds") or 900),
    }


def _authorization(project: Project, environment: str) -> dict[str, Any]:
    raw = _root_config(project).get(_AUTH_KEY)
    source = raw if isinstance(raw, dict) else {}
    env = normalize_environment(environment)
    item = source.get(env)
    if not isinstance(item, dict):
        item = {}
    return {
        "environment": env,
        "approved": bool(item.get("approved", False)),
        "approved_by": str(item.get("approved_by") or ""),
        "approved_at": str(item.get("approved_at") or ""),
        "note": str(item.get("note") or ""),
        "risk": deployment_risk(environment),
    }


def _save_authorization(
    project: Project,
    environment: str,
    *,
    approved: bool,
    actor: str,
    note: str,
) -> dict[str, Any]:
    root = _root_config(project)
    authorizations = root.get(_AUTH_KEY)
    if not isinstance(authorizations, dict):
        authorizations = {}
    env = normalize_environment(environment)
    authorizations[env] = {
        "approved": approved,
        "approved_by": actor if approved else "",
        "approved_at": datetime.now(timezone.utc).isoformat() if approved else "",
        "note": note.strip(),
    }
    root[_AUTH_KEY] = authorizations
    project.codex_config = json.dumps(root, ensure_ascii=False, separators=(",", ":"))
    return _authorization(project, environment)


def _read_action_file(action_id: str) -> dict[str, Any] | None:
    if not action_id or any(char not in "0123456789abcdef" for char in action_id.lower()):
        return None
    root = get_settings().host_actions_dir
    for directory in ("pending", "processed", "failed"):
        path = root / directory / f"{action_id}.json"
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if isinstance(payload, dict):
            if "status" not in payload:
                payload["status"] = "queued" if directory == "pending" else directory
            return payload
    return None


def _recent_project_action(project_id: str) -> dict[str, Any] | None:
    root = get_settings().host_actions_dir
    candidates: list[tuple[float, Path]] = []
    for directory in ("pending", "processed", "failed"):
        folder = root / directory
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            try:
                candidates.append((path.stat().st_mtime, path))
            except OSError:
                continue
    for _, path in sorted(candidates, key=lambda item: item[0], reverse=True)[:100]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if (
            isinstance(payload, dict)
            and payload.get("action") == "manual_deploy"
            and payload.get("project_id") == project_id
        ):
            return {
                key: payload.get(key)
                for key in (
                    "id",
                    "status",
                    "created_at",
                    "finished_at",
                    "detail",
                    "environment",
                    "risk",
                    "authorization",
                )
            }
    return None


@router.get("")
def list_manual_deployments(
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_deployments),
):
    projects = db.scalars(
        select(Project)
        .where(Project.workspace_id == principal.workspace_id)
        .order_by(Project.name)
    ).all()
    response = []
    for project in projects:
        config = _deploy_config(project)
        authorization = _authorization(project, config["environment"])
        decision = evaluate_deployment(
            principal.role,
            config["environment"],
            explicitly_approved=authorization["approved"],
        )
        response.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "project_slug": project.slug,
                "repository_url": project.repository_url,
                "default_branch": project.default_branch,
                "config": config,
                "authorization": authorization,
                "gate": {
                    "allowed": decision.allowed,
                    "risk": decision.risk,
                    "reason": decision.reason,
                    "requires_explicit_approval": decision.requires_explicit_approval,
                },
                "last_run": _recent_project_action(project.id),
            }
        )
    return response


@router.put("/{project_id}")
def save_manual_deployment(
    project_id: str,
    payload: ManualDeployConfig,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_deployments),
):
    project = _project(db, principal, project_id)
    previous = _deploy_config(project)
    root_config = _root_config(project)
    root_config[_CONFIG_KEY] = payload.model_dump()
    project.codex_config = json.dumps(root_config, ensure_ascii=False, separators=(",", ":"))

    if normalize_environment(previous["environment"]) != normalize_environment(payload.environment):
        _save_authorization(
            project,
            payload.environment,
            approved=False,
            actor=principal.actor,
            note="Autorização invalidada após mudança de ambiente de deploy.",
        )

    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=principal.actor,
        action="deployment.manual_config_updated",
        details={
            "environment": payload.environment,
            "branch": payload.branch,
            "workdir": payload.workdir,
            "enabled": payload.enabled,
            "timeout_seconds": payload.timeout_seconds,
            "risk": deployment_risk(payload.environment),
        },
    )
    db.commit()
    return {
        "project_id": project.id,
        "project_name": project.name,
        "config": payload.model_dump(),
        "authorization": _authorization(project, payload.environment),
    }


@router.put("/{project_id}/authorization")
def authorize_manual_deployment(
    project_id: str,
    payload: DeploymentAuthorizationInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_deployments),
):
    project = _project(db, principal, project_id)
    config = _deploy_config(project)
    authorization = _save_authorization(
        project,
        config["environment"],
        approved=payload.approved,
        actor=principal.actor,
        note=payload.note,
    )
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=principal.actor,
        action="deployment.authorization_updated",
        outcome="success" if payload.approved else "revoked",
        details={
            "environment": config["environment"],
            "risk": authorization["risk"],
            "approved": payload.approved,
            "note": payload.note.strip(),
        },
    )
    db.commit()
    return authorization


@router.post("/{project_id}/run", status_code=202)
def run_manual_deployment(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_deployments),
):
    project = _project(db, principal, project_id)
    raw = _deploy_config(project)
    try:
        config = ManualDeployConfig.model_validate(raw)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Configuração de deploy incompleta") from error
    if not config.enabled:
        raise HTTPException(status_code=409, detail="Deploy manual está desativado para este projeto")

    authorization = _authorization(project, config.environment)
    decision = evaluate_deployment(
        principal.role,
        config.environment,
        explicitly_approved=authorization["approved"],
    )
    if not decision.allowed:
        record(
            db,
            workspace_id=project.workspace_id,
            project_id=project.id,
            actor=principal.actor,
            action="deployment.blocked_by_authorization_gate",
            outcome="blocked",
            details={
                "environment": config.environment,
                "risk": decision.risk,
                "reason": decision.reason,
            },
        )
        db.commit()
        raise HTTPException(status_code=409, detail=decision.reason)

    request = queue_host_action(
        "manual_deploy",
        actor=principal.actor,
        project_id=project.id,
        workspace_id=project.workspace_id,
        project_name=project.name,
        environment=config.environment,
        branch=config.branch,
        workdir=config.workdir,
        command=config.command,
        timeout_seconds=config.timeout_seconds,
        risk=decision.risk,
        authorization={
            "approved": authorization["approved"],
            "approved_by": authorization["approved_by"],
            "approved_at": authorization["approved_at"],
        },
    )
    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=principal.actor,
        action="deployment.manual_queued",
        details={
            "host_action_id": request["id"],
            "environment": config.environment,
            "branch": config.branch,
            "workdir": config.workdir,
            "risk": decision.risk,
            "authorization": authorization,
        },
    )
    db.commit()
    return {
        "project_id": project.id,
        "project_name": project.name,
        "risk": decision.risk,
        "authorization": authorization,
        "host_action": request,
        "message": "Deploy autorizado e enviado para execução no host.",
    }


@router.get("/actions/{action_id}")
def manual_deployment_status(
    action_id: str,
    principal: Principal = Depends(manage_deployments),
):
    payload = _read_action_file(action_id)
    if not payload or payload.get("action") != "manual_deploy":
        raise HTTPException(status_code=404, detail="Execução de deploy não encontrada")
    if payload.get("workspace_id") != principal.workspace_id:
        raise HTTPException(status_code=404, detail="Execução de deploy não encontrada")
    return {
        key: payload.get(key)
        for key in (
            "id",
            "project_id",
            "project_name",
            "environment",
            "branch",
            "risk",
            "authorization",
            "status",
            "created_at",
            "finished_at",
            "detail",
        )
    }
