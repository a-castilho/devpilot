from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent
from app.security import Principal, Role, require_roles, session_principal
from app.services.audit import record


router = APIRouter(prefix="/api/admin/broadcast", tags=["admin-broadcast"])
manage_broadcast = require_roles(Role.SUPER_ADMIN)
_SCOPE_DISABLED_OPTION = "devpilot_account_scope_disabled"
_ACTION = "admin.broadcast.sent"


class BroadcastRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    level: str = Field(default="info", pattern="^(info|success|warning|critical)$")


def _details(event: AuditEvent) -> dict:
    try:
        value = json.loads(event.details or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _serialize(event: AuditEvent) -> dict:
    details = _details(event)
    return {
        "id": event.id,
        "message": str(details.get("message") or ""),
        "level": str(details.get("level") or "info"),
        "sender": str(details.get("sender") or "Super Admin"),
        "created_at": event.created_at,
    }


@router.get("")
def list_broadcasts(
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    """Return global Super Admin broadcasts to any authenticated connected user."""
    query = (
        select(AuditEvent)
        .where(AuditEvent.action == _ACTION, AuditEvent.outcome == "success")
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        .limit(50)
        .execution_options(**{_SCOPE_DISABLED_OPTION: True})
    )
    if since is not None:
        query = query.where(AuditEvent.created_at > since)
    items = list(db.scalars(query).all())
    return {
        "connected": True,
        "role": principal.role.value,
        "items": [_serialize(item) for item in items],
        "server_time": datetime.now(timezone.utc),
    }


@router.post("")
def send_broadcast(
    payload: BroadcastRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_broadcast),
):
    """Publish a persistent global message. Only SUPER_ADMIN can send."""
    message = payload.message.strip()
    if not message:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Mensagem não pode ficar vazia")

    event = record(
        db,
        workspace_id=str(principal.workspace_id),
        actor=principal.actor,
        action=_ACTION,
        details={
            "message": message,
            "level": payload.level,
            "sender": principal.email or "Super Admin",
            "scope": "all_connected_users",
        },
    )
    db.commit()
    db.refresh(event)
    return {"sent": True, "broadcast": _serialize(event)}
