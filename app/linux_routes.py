from __future__ import annotations

import hashlib
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential, Task
from app.security import Principal, Role, session_principal
from app.services.audit import record
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError
from app.services.vault import Vault


router = APIRouter(prefix="/api/linux", tags=["linux"])

_GITHUB_CLOUD_PROVIDER = "cloud:github"
_CLOUD_CREDENTIAL_LABEL = "cloud-admin"
_GAME_MARKER = "[DEVPILOT_BUILD_GAME_V1]"
_GAME_PHASE_RE = re.compile(r"^FASE:\s*(\d+)/7\s*$", re.IGNORECASE | re.MULTILINE)
_GAME_PHASE_XP = {1: 100, 2: 220, 3: 100, 4: 160, 5: 80, 6: 100, 7: 140}
_TERMINAL_BONUS_PHASES = {1, 2, 3}
_TERMINAL_BONUS_XP = sum(_GAME_PHASE_XP[phase] for phase in _TERMINAL_BONUS_PHASES)
_TERMINAL_BONUS_ROLES = {Role.OWNER, Role.ADMIN, Role.ANALYST}


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


def _task_phase(task: object) -> int | None:
    prompt = str(getattr(task, "prompt", "") or "")
    if _GAME_MARKER not in prompt:
        return None
    match = _GAME_PHASE_RE.search(prompt)
    if not match:
        return None
    phase = int(match.group(1))
    return phase if phase in _GAME_PHASE_XP else None


def _task_completed(task: object) -> bool:
    status = getattr(task, "status", "")
    value = getattr(status, "value", status)
    return str(value or "").strip().lower() == "completed"


def _linux_bonus_from_tasks(tasks: list[object], role: Role) -> dict:
    if role is Role.SUPER_ADMIN:
        return {
            "eligible": True,
            "unlocked": True,
            "source": "super-admin",
            "required_phase": 0,
            "required_phases": [],
            "required_xp": 0,
            "earned_xp": 0,
            "completed_phases": [],
            "scope": "all-devpilot-linux-sessions",
            "message": "Super Admin possui acesso a todas as sessões Linux gerenciadas pelo DevPilot.",
        }

    eligible = role in _TERMINAL_BONUS_ROLES
    completed_phases = {
        phase
        for task in tasks
        if _task_completed(task) and (phase := _task_phase(task)) is not None
    }
    earned_xp = sum(_GAME_PHASE_XP[phase] for phase in sorted(completed_phases))
    unlocked = eligible and _TERMINAL_BONUS_PHASES.issubset(completed_phases)

    if not eligible:
        message = (
            "O perfil VIEWER é somente leitura e não recebe terminal executável."
            if role is Role.VIEWER
            else "Este perfil não está habilitado para executar terminal Linux."
        )
    elif unlocked:
        message = "Bônus do jogo liberado: Terminal Linux em workspace isolado."
    else:
        message = (
            "Conclua as fases 1, 2 e 3 do Jogo de construção "
            f"para liberar o Terminal Linux ({_TERMINAL_BONUS_XP} XP)."
        )

    return {
        "eligible": eligible,
        "unlocked": unlocked,
        "source": "build-game",
        "required_phase": max(_TERMINAL_BONUS_PHASES),
        "required_phases": sorted(_TERMINAL_BONUS_PHASES),
        "required_xp": _TERMINAL_BONUS_XP,
        "earned_xp": earned_xp,
        "completed_phases": sorted(completed_phases),
        "scope": "own-isolated-workspace",
        "message": message,
    }


def _terminal_bonus_status(db: Session, principal: Principal) -> dict:
    if principal.role is Role.SUPER_ADMIN:
        return _linux_bonus_from_tasks([], principal.role)
    tasks = list(
        db.scalars(
            select(Task).where(
                Task.workspace_id == principal.workspace_id,
                Task.owner_user_id == principal.user_id,
                Task.prompt.contains(_GAME_MARKER),
            )
        ).all()
    )
    return _linux_bonus_from_tasks(tasks, principal.role)


def require_terminal_bonus(db: Session, principal: Principal) -> dict:
    bonus = _terminal_bonus_status(db, principal)
    if not bonus["unlocked"]:
        raise HTTPException(status_code=403, detail=bonus["message"])
    return bonus


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


def require_owned_session(
    db: Session,
    principal: Principal,
    session_id: str,
) -> dict:
    require_terminal_bonus(db, principal)
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
    terminal_bonus = _terminal_bonus_status(db, principal)
    profile = {
        "user_id": principal.user_id,
        "workspace_id": principal.workspace_id,
        "workspace_key": None if super_admin else workspace_key(principal),
        "role": principal.role.value,
        "mode": "dedicated-linux-user" if super_admin else "isolated-user-workspace",
        "linux_user": None,
        "linux_user_ready": False,
        "git_cloud": _github_cloud_status(github_cloud) if super_admin else None,
        "terminal_bonus": terminal_bonus,
        "admin_scope": "all-devpilot-linux-sessions" if super_admin else None,
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
def terminal_sessions(
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    require_terminal_bonus(db, principal)
    items = [session for session in _all_sessions() if _can_access_session(principal, session)]
    return {
        "items": items,
        "scope": "all-devpilot-linux-sessions"
        if principal.role is Role.SUPER_ADMIN
        else "own-isolated-workspace",
    }


@router.post("/terminal/sessions", status_code=201)
def create_terminal_session(
    payload: TerminalCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    terminal_bonus = require_terminal_bonus(db, principal)
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
            "mode": "dedicated-linux-user"
            if principal.role is Role.SUPER_ADMIN
            else "isolated-user-workspace",
            "git_provider": session.get("git_provider"),
            "git_cloud_integrated": bool(git_auth),
            "terminal_bonus_source": terminal_bonus.get("source"),
            "terminal_bonus_scope": terminal_bonus.get("scope"),
        },
    )
    db.commit()
    return {
        **session,
        "access_scope": terminal_bonus["scope"],
        "game_bonus": terminal_bonus,
    }


@router.get("/terminal/sessions/{session_id}/output")
def terminal_output(
    session_id: str,
    after: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    require_owned_session(db, principal, session_id)
    return agent_call("GET", f"/v1/terminal/sessions/{session_id}/output?after={after}")


@router.post("/terminal/sessions/{session_id}/input")
def terminal_input(
    session_id: str,
    payload: TerminalInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    target_session = require_owned_session(db, principal, session_id)
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
            "super_admin_cross_session": principal.role is Role.SUPER_ADMIN,
            "target_actor": target_session.get("actor"),
        },
    )
    db.commit()
    return result


@router.post("/terminal/sessions/{session_id}/resize")
def terminal_resize(
    session_id: str,
    payload: TerminalResize,
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_user),
):
    require_owned_session(db, principal, session_id)
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
    target_session = require_owned_session(db, principal, session_id)
    result = agent_call("DELETE", f"/v1/terminal/sessions/{session_id}")
    audit(
        db,
        principal,
        action="linux.terminal_session_closed",
        details={
            "session_id": session_id,
            "exit_code": result.get("exit_code"),
            "super_admin_cross_session": principal.role is Role.SUPER_ADMIN,
            "target_actor": target_session.get("actor"),
        },
    )
    db.commit()
    return result
