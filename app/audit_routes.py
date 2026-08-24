from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent
from app.security import Principal, session_principal
from app.services.audit import verify_chain
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError


router = APIRouter(prefix="/api/audit", tags=["audit"])
_SCOPE_DISABLED_OPTION = "devpilot_account_scope_disabled"


def current_principal(principal: Principal = Depends(session_principal)) -> Principal:
    if not principal.user_id or not principal.workspace_id:
        raise HTTPException(status_code=401, detail="Sessão de usuário inválida")
    return principal


@router.get("/linux-identity")
def audit_linux_identity(_: Principal = Depends(current_principal)):
    try:
        identity = LinuxAgentClient().request("GET", "/v1/audit/identity")
    except LinuxAgentError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return {
        "connected": True,
        "audit": identity,
    }


@router.get("/integrity")
def audit_integrity(
    db: Session = Depends(get_db),
    principal: Principal = Depends(current_principal),
):
    # Integrity validates the single workspace-global chain. Account-level filtering
    # applies to normal audit history reads, but not to this aggregate hash check.
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == principal.workspace_id)
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        .execution_options(**{_SCOPE_DISABLED_OPTION: True})
    ).all()
    result = verify_chain(events)
    result["workspace_id"] = principal.workspace_id
    try:
        identity = LinuxAgentClient().request("GET", "/v1/audit/identity")
        result["current_linux_identity"] = identity
    except LinuxAgentError as error:
        result["current_linux_identity"] = None
        result["linux_agent_error"] = str(error)
    return result
