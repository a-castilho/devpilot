from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Workspace
from app.schemas import VoiceCommand
from app.security import require_access, require_super_admin
from app.services.audit import record
from app.services.host_actions import queue_host_action
from app.services.intent import interpret_voice
from app.services.runner_status import runner_status


router = APIRouter(prefix="/api/voice", dependencies=[Depends(require_access)])


def workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


@router.get("/runner-status")
def github_actions_runner_status(actor: str = Depends(require_super_admin)):
    del actor
    return runner_status()


@router.post("/system-actions", status_code=202)
def voice_system_action(
    payload: VoiceCommand,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    intent = interpret_voice(payload.transcript)
    if intent.get("action") != "update_local":
        raise HTTPException(422, "Comando de sistema não permitido")

    ws = workspace(db)
    request = queue_host_action(
        "update_local",
        transcript=payload.transcript,
        actor=actor,
    )
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="voice.host_action_queued",
        details={
            "host_action_id": request["id"],
            "action": request["action"],
            "transcript": payload.transcript,
        },
    )
    db.commit()
    return {
        "intent": intent,
        "host_action": request,
        "message": "Atualização local enviada ao Linux.",
    }
