from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import get_settings


# Host actions are intentionally closed over a small set of named operations.
# Never accept free-form commands here: the host runner executes outside the
# application container and must remain a strict privilege boundary.
ALLOWED_HOST_ACTIONS = {"update_local"}


def queue_host_action(action: str, *, actor: str, transcript: str = "", **data) -> dict:
    if action not in ALLOWED_HOST_ACTIONS:
        raise ValueError(f"Host action is not allowed: {action}")

    settings = get_settings()
    request_id = uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    payload = {
        **data,
        "id": request_id,
        "action": action,
        "actor": actor,
        "created_at": created_at,
    }
    if transcript:
        payload["transcript"] = transcript

    pending = settings.host_actions_dir / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    target = pending / f"{request_id}.json"
    temporary = pending / f".{request_id}.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)

    return {
        "id": request_id,
        "action": action,
        "status": "queued",
        "created_at": created_at,
        "queue_file": str(Path("pending") / target.name),
    }
