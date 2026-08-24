from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential
from app.security import Principal, Role, session_principal
from app.services.audit import record
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError
from app.services.vault import Vault


router = APIRouter(prefix="/api/linux", tags=["linux"])

_GITHUB_CLOUD_PROVIDER = "cloud:github"
_CLOUD_CREDENTIAL_LABEL = "cloud-admin"


class TerminalCreate(BaseModel):
    cwd: str | None = Field(default=None, max_length=4096)
    columns: int = Field(default=120, ge=20, le=400)
    rows: int = Field(default=34, ge=5, le=200)


class TerminalInput(BaseModel):
    data: str = Field(min_length=1, max_length=100_000)


class TerminalResize(BaseModel):
    columns: int = Field(ge=20, le=400)
    rows: int = Field(ge=5, le=200)


def current_user(principal: Principal = Depends(session_principal)) -> Principal:
    if not principal.user_id or not principal.workspace_id:
        raise HTTPException(status_code=401, detail="Sessão de usuário inválida")
    return principal


def workspace_key(principal: Principal) -> str:
    raw = f"{principal.workspace_id}:{principal.user_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def agent_call(method: str, path: str, *, payload: dict | None = None) -> dict:
    try:
        return LinuxAgentClient().request(method, path, payload=payload)
    except LinuxAgentError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


def audit(
    db: Session,
    principal: Principal,
    *,
    action: str,
    details: dict,
) -> None:
    if not principal.workspace_id:
        return
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action=action,
        details=details,
    )


def _github_cloud_credential(
    db: Session,
    principal: Principal,
) -> ProviderCredential | None:
    if principal.role is not Role.SUPER_ADMIN:
        return None
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == principal.workspace_id,
            ProviderCredential.provider == _GITHUB_CLOUD_PROVIDER,
            ProviderCredential.label == _CLOUD_CREDENTIAL_LABEL,
        )
    )


def _github_cloud_scope(item: ProviderCredential | None) -> str:
    if not item:
        return ""
    try:
        metadata = json.loads(item.models or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return ""
    return str(metadata.get("scope") or "") if isinstance(metadata, dict) else ""


def _github_cloud_status(item: ProviderCredential | None) -> dict:
    configured = item is not None
    enabled = bool(item.enabled) if item else False
    return {
        "provider": "github",
        "host": "github.com",
        "configured": configured,
        "enabled": enabled,
        "ready": configured and enabled,
        "scope": _github_cloud_scope(item),
        "source": "clouds",
    }


def _github_terminal_auth(item: ProviderCredential | None) -> dict | None:
    if not item or not item.enabled:
        return None
    try:
        token = Vault().decrypt(item.encrypted_secret).strip()
    except ValueError as error:
        raise HTTPException(
            status_code=503,
            detail="A credencial GitHub cadastrada em Clouds não pôde ser carregada",
        ) from error
    if len(token) < 8:
        raise HTTPException(
            status_code=503,
            detail="A credencial GitHub cadastrada em Clouds é inválida",
        )
    return {
        "provider": "github",
        "host": "github.com",
        "token": token,
        "scope": _github_cloud_scope(item),
    }


def _all_sessions() -> list[dict]:
    data = agent_call("GET", "/v1/terminal/sessions")
    return list(data.get("items") or [])


def _can_access_session(principal: Principal, session: dict) -> bool:
    return principal.role is Role.SUPER_ADMIN or session.get("actor") == principal.actor


def require_owned_session(principal: Principal, session_id: str) -> dict:
    for session in _all_sessions():
        if session.get("id") == session_id:
            if not _can_access_session(principal, session):
                raise HTTPException(status_code=403, detail="Sessão Linux pertence a outro usuário")
            return session
    raise HTTPException(status_code=404, detail="Sessão Linux não encontrada")


@router.get("/status")
def linux_status(
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    super_admin = principal.role is Role.SUPER_ADMIN
    github_cloud = _github_cloud_credential(db, principal)
    profile = {
        "user_id": principal.user_id,
        "workspace_id": principal.workspace_id,
        "workspace_key": None if super_admin else workspace_key(principal),
        "role": principal.role.value,
        "mode": "dedicated-linux-user" if super_admin else "isolated-user-workspace",
        "linux_user": None,
        "linux_user_ready": False,
        "git_cloud": _github_cloud_status(github_cloud) if super_admin else None,
    }
    try:
        health = LinuxAgentClient().health()
    except LinuxAgentError as error:
        return {
            "connected": False,
            "error": str(error),
            "agent": None,
            "system": None,
            "profile": profile,
        }

    terminal_user = health.get("terminal_user") or {}
    if super_admin:
        profile["linux_user"] = terminal_user.get("username")
        profile["linux_user_ready"] = bool(terminal_user.get("ready"))

    if health.get("status") != "ok":
        reason = terminal_user.get("reason")
        return {
            "connected": False,
            "error": str(reason or "Linux Agent requer configuração"),
            "agent": health,
            "system": None,
            "profile": profile,
        }

    return {
        "connected": True,
        "error": None,
        "agent": health,
        "system": agent_call("GET", "/v1/system"),
        "profile": profile,
    }


@router.get("/terminal/sessions")
def terminal_sessions(principal: Principal = Depends(current_user)):
    items = [session for session in _all_sessions() if _can_access_session(principal, session)]
    return {"items": items}


@router.post("/terminal/sessions", status_code=201)
def create_terminal_session(
    payload: TerminalCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    if payload.cwd and principal.role is not Role.SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Diretório inicial manual é exclusivo do Super Admin; seu perfil usa workspace isolado",
        )

    request_payload = {
        "actor": principal.actor,
        "columns": payload.columns,
        "rows": payload.rows,
    }
    git_auth = None
    if principal.role is Role.SUPER_ADMIN:
        if payload.cwd:
            request_payload["cwd"] = payload.cwd
        git_auth = _github_terminal_auth(_github_cloud_credential(db, principal))
        if git_auth:
            request_payload["git_auth"] = git_auth
    else:
        request_payload["workspace_key"] = workspace_key(principal)

    session = agent_call("POST", "/v1/terminal/sessions", payload=request_payload)
    audit(
        db,
        principal,
        action="linux.terminal_session_created",
        details={
            "session_id": session.get("id"),
            "cwd": session.get("cwd"),
            "pid": session.get("pid"),
            "linux_user": session.get("linux_user"),
            "workspace_key": None if principal.role is Role.SUPER_ADMIN else workspace_key(principal),
            "mode": "dedicated-linux-user" if principal.role is Role.SUPER_ADMIN else "isolated-user-workspace",
            "git_provider": session.get("git_provider"),
            "git_cloud_integrated": bool(git_auth),
        },
    )
    db.commit()
    return session


@router.get("/terminal/sessions/{session_id}/output")
def terminal_output(
    session_id: str,
    after: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_user),
):
    require_owned_session(principal, session_id)
    return agent_call("GET", f"/v1/terminal/sessions/{session_id}/output?after={after}")


@router.post("/terminal/sessions/{session_id}/input")
def terminal_input(
    session_id: str,
    payload: TerminalInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    require_owned_session(principal, session_id)
    result = agent_call(
        "POST",
        f"/v1/terminal/sessions/{session_id}/input",
        payload={"data": payload.data},
    )
    audit(
        db,
        principal,
        action="linux.terminal_input",
        details={
            "session_id": session_id,
            "bytes": len(payload.data.encode("utf-8")),
            "sha256": hashlib.sha256(payload.data.encode("utf-8")).hexdigest(),
        },
    )
    db.commit()
    return result


@router.post("/terminal/sessions/{session_id}/resize")
def terminal_resize(
    session_id: str,
    payload: TerminalResize,
    principal: Principal = Depends(current_user),
):
    require_owned_session(principal, session_id)
    return agent_call(
        "POST",
        f"/v1/terminal/sessions/{session_id}/resize",
        payload=payload.model_dump(),
    )


@router.delete("/terminal/sessions/{session_id}")
def close_terminal_session(
    session_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    require_owned_session(principal, session_id)
    result = agent_call("DELETE", f"/v1/terminal/sessions/{session_id}")
    audit(
        db,
        principal,
        action="linux.terminal_session_closed",
        details={
            "session_id": session_id,
            "exit_code": result.get("exit_code"),
        },
    )
    db.commit()
    return result
