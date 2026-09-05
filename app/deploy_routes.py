from __future__ import annotations

import json
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


router = APIRouter(prefix="/api/admin/deployments", tags=["admin-deployments"])
manage_deployments = require_roles(Role.SUPER_ADMIN)
_CONFIG_KEY = "manual_deploy"
_LEGACY_DEPLOY_DISABLED = (
    "Deploy manual por comando foi desativado por segurança. "
    "Use um fluxo de deploy estruturado por provedor/CI ou uma ação de host nomeada."
)


class ManualDeployConfig(BaseModel):
    enabled: bool = False
    environment: str = Field(default="homolog", min_length=1, max_length=40)
    branch: str = Field(default="main", min_length=1, max_length=120)
    workdir: str = Field(default="", min_length=1, max_length=500)
    timeout_seconds: int = Field(default=900, ge=30, le=3600)

    @field_validator("environment", "branch", "workdir")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Campo obrigatório")
        if "\x00" in value:
            raise ValueError("Valor inválido")
        return value


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
            "timeout_seconds": 900,
        }
    return {
        "enabled": bool(raw.get("enabled", False)),
        "environment": str(raw.get("environment") or "homolog"),
        "branch": str(raw.get("branch") or project.default_branch or "main"),
        "workdir": str(raw.get("workdir") or ""),
        "timeout_seconds": int(raw.get("timeout_seconds") or 900),
    }


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
                for key in ("id", "status", "created_at", "finished_at", "detail", "environment")
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
    return [
        {
            "project_id": project.id,
            "project_name": project.name,
            "project_slug": project.slug,
            "repository_url": project.repository_url,
            "default_branch": project.default_branch,
            "config": _deploy_config(project),
            "manual_execution_available": False,
            "manual_execution_reason": _LEGACY_DEPLOY_DISABLED,
            "last_run": _recent_project_action(project.id),
        }
        for project in projects
    ]


@router.put("/{project_id}")
def save_manual_deployment(
    project_id: str,
    payload: ManualDeployConfig,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_deployments),
):
    project = _project(db, principal, project_id)
    root_config = _root_config(project)
    root_config[_CONFIG_KEY] = payload.model_dump()
    project.codex_config = json.dumps(root_config, ensure_ascii=False, separators=(",", ":"))

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
            "shell_command_supported": False,
        },
    )
    db.commit()
    return {
        "project_id": project.id,
        "project_name": project.name,
        "config": payload.model_dump(),
        "manual_execution_available": False,
        "manual_execution_reason": _LEGACY_DEPLOY_DISABLED,
    }


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

    record(
        db,
        workspace_id=project.workspace_id,
        project_id=project.id,
        actor=principal.actor,
        action="deployment.manual_blocked",
        outcome="blocked",
        details={
            "reason": "legacy_shell_command_disabled",
            "environment": config.environment,
            "branch": config.branch,
            "workdir": config.workdir,
        },
    )
    db.commit()
    raise HTTPException(status_code=409, detail=_LEGACY_DEPLOY_DISABLED)


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
            "status",
            "created_at",
            "finished_at",
            "detail",
        )
    }
