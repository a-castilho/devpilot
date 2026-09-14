from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app import product_delivery_routes as delivery
from app.db import SessionLocal
from app.delivery_url_recovery import install_delivery_url_recovery
from app.models import Project, ProjectStatus


_RECOVERABLE_STATUSES = {"pending", "blocked", "failed", "deploying", "provisioning", "repairing"}
_RETRY_SECONDS = {
    "pending": 5,
    "failed": 20,
    "deploying": 15,
    "provisioning": 15,
    "repairing": 15,
    "blocked": 60,
}
_MAX_PROJECT_SCAN = 100


def _delivery_state(project: Project) -> dict | None:
    try:
        config = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(config, dict):
        return None
    state = config.get("delivery")
    return state if isinstance(state, dict) else None


def _timestamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _due(state: dict, now: datetime) -> bool:
    status = str(state.get("status") or "").strip().lower()
    if status not in _RECOVERABLE_STATUSES:
        return False
    updated_at = _timestamp(state.get("updated_at"))
    if updated_at is None:
        return True
    retry_after = _RETRY_SECONDS.get(status, 30)
    return (now - updated_at).total_seconds() >= retry_after


def process_delivery_recovery_once() -> bool:
    """Advance one persisted delivery without depending on an open browser.

    Delivery provider functions are idempotent: existing Render services, Vercel
    deployment IDs and persisted public URLs are reused before a new resource is
    created. Processing only one due project per idle worker cycle also prevents a
    cloud-provider request storm when several projects are waiting at once.
    """
    install_delivery_url_recovery()
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        projects = db.scalars(
            select(Project)
            .where(Project.status == ProjectStatus.active)
            .order_by(Project.created_at.asc())
            .limit(_MAX_PROJECT_SCAN)
        ).all()

        for project in projects:
            state = _delivery_state(project)
            if not state or not _due(state, now):
                continue

            try:
                delivery.run_delivery(db, project, "worker:delivery-recovery")
            except Exception as error:  # keep the task worker alive on provider/runtime faults
                print(
                    f"[worker] delivery recovery failed project={project.id}: {error}",
                    flush=True,
                )
            return True

    return False
