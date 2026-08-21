from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import Principal, Role, require_roles
from app.services.audit import record
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError


router = APIRouter(prefix="/api/linux", tags=["linux"])


class TerminalCreate(BaseModel):
    cwd: str | None = Field(default=None, max_length=4096)
    columns: int = Field(default=120, ge=20, le=400)
    rows: int = Field(default=34, ge=5, le=200)


class TerminalInput(BaseModel):
    data: str = Field(min_length=1, max_length=100_000)


class TerminalResize(BaseModel):
    columns: int = Field(ge=20, le=400)
    rows: int = Field(ge=5, le=200)


def super_admin(
    principal: Principal = Depends(require_roles(Role.SUPER_ADMIN)),
) -> Principal:
    return principal


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


@router.get("/status")
def linux_status(principal: Principal = Depends(super_admin)):
    try:
        health = LinuxAgentClient().health()
    except LinuxAgentError as error:
        return {
            "connected": False,
            "error": str(error),
            "agent": None,
            "system": None,
        }

    if health.get("status") != "ok":
        return {
            "connected": False,
            "error": "Linux Agent requer configuração",
            "agent": health,
            "system": None,
        }

    return {
        "connected": True,
        "error": None,
        "agent": health,
        "system": agent_call("GET", "/v1/system"),
    }


@router.get("/terminal/sessions")
def terminal_sessions(principal: Principal = Depends(super_admin)):
    return agent_call("GET", "/v1/terminal/sessions")


@router.post("/terminal/sessions", status_code=201)
def create_terminal_session(
    payload: TerminalCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(super_admin),
):
    session = agent_call(
        "POST",
        "/v1/terminal/sessions",
        payload={
            "actor": principal.actor,
            "cwd": payload.cwd,
            "columns": payload.columns,
            "rows": payload.rows,
        },
    )
    audit(
        db,
        principal,
        action="linux.terminal_session_created",
        details={
            "session_id": session.get("id"),
            "cwd": session.get("cwd"),
            "pid": session.get("pid"),
        },
    )
    db.commit()
    return session


@router.get("/terminal/sessions/{session_id}/output")
def terminal_output(
    session_id: str,
    after: int = Query(default=0, ge=0),
    principal: Principal = Depends(super_admin),
):
    return agent_call(
        "GET",
        f"/v1/terminal/sessions/{session_id}/output?after={after}",
    )


@router.post("/terminal/sessions/{session_id}/input")
def terminal_input(
    session_id: str,
    payload: TerminalInput,
    db: Session = Depends(get_db),
    principal: Principal = Depends(super_admin),
):
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
    principal: Principal = Depends(super_admin),
):
    return agent_call(
        "POST",
        f"/v1/terminal/sessions/{session_id}/resize",
        payload=payload.model_dump(),
    )


@router.delete("/terminal/sessions/{session_id}")
def close_terminal_session(
    session_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(super_admin),
):
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
