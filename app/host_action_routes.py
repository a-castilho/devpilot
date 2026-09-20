from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import VoiceCommand
from app.security import Principal, require_access, require_super_admin, session_principal
from app.services.audit import record
from app.services.host_actions import queue_host_action
from app.services.intent import interpret_voice
from app.services.runner_status import runner_status
from app.services.workspace_scope import workspace_for_principal


router = APIRouter(prefix="/api/voice", dependencies=[Depends(require_access)])


@router.get("/runner-status")
def github_actions_runner_status(actor: str = Depends(require_super_admin)):
    del actor
    return runner_status()


@router.post("/system-actions", status_code=202)
def voice_system_action(
    payload: VoiceCommand,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_super_admin),
):
    intent = interpret_voice(payload.transcript)
    if intent.get("action") != "update_local":
        raise HTTPException(422, "Comando de sistema não permitido")

    ws = workspace_for_principal(db, principal)
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
