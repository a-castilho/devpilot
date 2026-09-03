from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Run, Task, TaskStatus
from app.security import Principal, Role, require_roles
from app.services.audit import record

router = APIRouter(prefix="/api/admin/pipeline-repair", tags=["admin-pipeline-repair"])
manage_pipeline_repair = require_roles(Role.SUPER_ADMIN)


def _queue_dirs() -> tuple[Path, Path, Path]:
    root = get_settings().host_actions_dir
    pending = root / "pending"
    processed = root / "processed"
    failed = root / "failed"
    for directory in (pending, processed, failed):
        directory.mkdir(parents=True, exist_ok=True)
    return pending, processed, failed


def _latest_action() -> dict:
    pending, processed, failed = _queue_dirs()
    files = [*pending.glob("pipeline-repair-*.json"), *processed.glob("pipeline-repair-*.json"), *failed.glob("pipeline-repair-*.json")]
    if not files:
        return {}
    latest = max(files, key=lambda item: item.stat().st_mtime)
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return {"id": latest.stem, "status": "unknown", "detail": "Resultado não pôde ser lido."}
    payload["queue"] = latest.parent.name
    payload["detail"] = str(payload.get("detail") or "")[-4000:]
    return payload


def _diagnostics(db: Session, principal: Principal) -> dict:
    queued = db.scalar(
        select(func.count(Task.id)).where(
            Task.workspace_id == principal.workspace_id,
            Task.status == TaskStatus.queued,
        )
    ) or 0
    running = db.scalar(
        select(func.count(Task.id)).where(
            Task.workspace_id == principal.workspace_id,
            Task.status == TaskStatus.running,
        )
    ) or 0
    failed = db.scalar(
        select(func.count(Task.id)).where(
            Task.workspace_id == principal.workspace_id,
            Task.status.in_([TaskStatus.failed, TaskStatus.blocked]),
        )
    ) or 0
    latest_run = db.scalar(
        select(Run)
        .join(Task, Task.id == Run.task_id)
        .where(Task.workspace_id == principal.workspace_id)
        .order_by(Run.started_at.desc())
        .limit(1)
    )
    latest = _latest_action()
    latest_detail = str(latest.get("detail") or "")
    dns_failure = "failed to resolve host 'postgres'" in latest_detail.lower() or "name or service not known" in latest_detail.lower()
    return {
        "authorized": True,
        "role": principal.role.value,
        "queue": {"queued": int(queued), "running": int(running), "failed": int(failed)},
        "latest_run": {
            "id": latest_run.id if latest_run else None,
            "status": latest_run.status if latest_run else None,
            "started_at": latest_run.started_at.isoformat() if latest_run and latest_run.started_at else None,
        },
        "latest_repair": latest,
        "checks": [
            {"id": "database", "label": "Banco do DevPilot", "ok": True, "detail": "API conectada ao banco atual."},
            {"id": "queue", "label": "Fila de execução", "ok": int(queued) == 0 or int(running) > 0, "detail": f"{int(queued)} na fila · {int(running)} executando"},
            {"id": "worker_dns", "label": "DNS do worker para postgres", "ok": not dns_failure, "detail": "Falha conhecida detectada no último reparo." if dns_failure else "Sem falha de DNS registrada no último reparo."},
        ],
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("")
def pipeline_repair_context(
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_pipeline_repair),
):
    return _diagnostics(db, principal)


@router.post("/run", status_code=202)
def run_pipeline_repair(
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_pipeline_repair),
):
    pending, _, _ = _queue_dirs()
    action_id = f"pipeline-repair-{uuid.uuid4()}"
    payload = {
        "id": action_id,
        "action": "pipeline_repair",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": principal.actor,
        "workspace_id": principal.workspace_id,
        "status": "pending",
    }
    target = pending / f"{action_id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="pipeline_repair.requested",
        outcome="pending",
        details={"action_id": action_id},
    )
    db.commit()
    return {"accepted": True, "action_id": action_id, "status": "pending"}
