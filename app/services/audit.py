import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent


def record(
    db: Session,
    *,
    workspace_id: str,
    actor: str,
    action: str,
    details: dict,
    project_id: str | None = None,
    task_id: str | None = None,
    outcome: str = "success",
) -> AuditEvent:
    previous = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == workspace_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(1)
    )
    previous_hash = previous.event_hash if previous else ""
    serialized = json.dumps(details, sort_keys=True, separators=(",", ":"), default=str)
    fingerprint = "|".join(
        [previous_hash, workspace_id, project_id or "", task_id or "", actor, action, outcome, serialized]
    )
    event = AuditEvent(
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task_id,
        actor=actor,
        action=action,
        outcome=outcome,
        details=serialized,
        previous_hash=previous_hash,
        event_hash=hashlib.sha256(fingerprint.encode()).hexdigest(),
    )
    db.add(event)
    return event
