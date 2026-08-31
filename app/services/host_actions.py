from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import get_settings


RESOURCE_JOB_ACTION = "resource_job"
ALLOWED_HOST_ACTIONS = {"update_local", "manual_deploy", RESOURCE_JOB_ACTION}


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


def queue_resource_job(
    command: str,
    *,
    actor: str,
    workdir: str,
    timeout_seconds: int = 900,
    project_id: str = "",
    project_name: str = "",
    branch: str = "",
) -> dict:
    """Queue an auxiliary build/test job for the host resource router.

    The host runner performs the authoritative command allow-list check. Keeping
    the SSH credentials and routing logic on the host avoids mounting host SSH
    material into the DevPilot containers.
    """
    normalized = str(command or "").strip()
    if not normalized:
        raise ValueError("Resource job command cannot be empty")

    return queue_host_action(
        RESOURCE_JOB_ACTION,
        actor=actor,
        command=normalized,
        workdir=workdir,
        timeout_seconds=min(max(int(timeout_seconds), 30), 3600),
        project_id=project_id,
        project_name=project_name,
        branch=branch,
    )
