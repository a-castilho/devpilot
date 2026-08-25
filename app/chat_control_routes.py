from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Workspace
from app.platform_models import PlatformControl
from app.security import require_access, require_super_admin
from app.services.audit import record


router = APIRouter(prefix="/api")
CHAT_CONTROL_KEY = "devpilot.chat"
DEFAULT_CHAT_ENABLED = False
DEFAULT_CHAT_REASON = "Chat desligado por padrão pelo controle da plataforma."


class ChatControlUpdate(BaseModel):
    enabled: bool
    reason: str = Field(default="", max_length=500)


def chat_control(db: Session) -> PlatformControl | None:
    return db.scalar(select(PlatformControl).where(PlatformControl.key == CHAT_CONTROL_KEY))


def chat_enabled(db: Session) -> bool:
    item = chat_control(db)
    return bool(item.enabled) if item is not None else DEFAULT_CHAT_ENABLED


def serialize_chat_control(item: PlatformControl | None) -> dict:
    if item is None:
        return {
            "key": CHAT_CONTROL_KEY,
            "enabled": DEFAULT_CHAT_ENABLED,
            "reason": DEFAULT_CHAT_REASON,
            "updated_by": "system-default",
            "updated_at": None,
            "source": "default",
        }
    return {
        "key": item.key,
        "enabled": bool(item.enabled),
        "reason": item.reason or "",
        "updated_by": item.updated_by,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "source": "stored",
    }


def _audit_workspace(db: Session) -> Workspace | None:
    return db.scalar(select(Workspace).order_by(Workspace.created_at.asc()))


@router.get("/chat/control")
def read_chat_control(
    db: Session = Depends(get_db),
    _actor: str = Depends(require_access),
):
    return serialize_chat_control(chat_control(db))


@router.put("/super-admin/chat/control")
def update_chat_control(
    payload: ChatControlUpdate,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    item = chat_control(db)
    previous = serialize_chat_control(item)
    if item is None:
        item = PlatformControl(key=CHAT_CONTROL_KEY)
        db.add(item)

    item.enabled = bool(payload.enabled)
    item.reason = payload.reason.strip() or (
        "Chat liberado pelo Super Admin."
        if payload.enabled
        else "Chat desligado pelo Super Admin."
    )
    item.updated_by = actor
    db.flush()

    workspace = _audit_workspace(db)
    if workspace is not None:
        record(
            db,
            workspace_id=workspace.id,
            actor=actor,
            action="platform.chat_control.updated",
            details={
                "previous_enabled": previous["enabled"],
                "enabled": item.enabled,
                "reason": item.reason,
                "scope": "platform",
            },
        )

    db.commit()
    db.refresh(item)
    return serialize_chat_control(item)
