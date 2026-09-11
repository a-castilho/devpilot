from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

_STARTED = False
_RECONCILE_SECONDS = 30
_INITIAL_DELAY_SECONDS = 15
_FAILED_RETRY_SECONDS = 300
# Delivery is mandatory and self-healing. waiting_code is a normal state: the
# implementation has not published the deployable revision yet, so no cloud
# provider should be called until the repository becomes ready.
_ACTIVE_STATES = {"pending", "provisioning", "deploying", "waiting_code", "blocked", "failed"}


def _delivery_payload(project) -> dict:
    try:
        config = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(config, dict):
        return {}
    delivery = config.get("delivery")
    return delivery if isinstance(delivery, dict) else {}


def _delivery_status(project) -> str:
    delivery = _delivery_payload(project)
    return str(delivery.get("status") or "pending").strip().lower()


def _retry_due(project, *, force: bool = False) -> bool:
    if force:
        return True
    delivery = _delivery_payload(project)
    status = str(delivery.get("status") or "pending").strip().lower()
    if status not in {"failed", "blocked"}:
        return True
    raw = str(delivery.get("updated_at") or "").strip()
    if not raw:
        return True
    try:
        updated = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - updated).total_seconds() >= _FAILED_RETRY_SECONDS


def _run() -> None:
    time.sleep(_INITIAL_DELAY_SECONDS)
    first_pass = True
    while True:
        try:
            from sqlalchemy import select

            from app import product_delivery_routes as delivery
            from app.db import SessionLocal
            from app.models import Project, ProjectStatus

            with SessionLocal() as db:
                projects = list(
                    db.scalars(
                        select(Project).where(
                            Project.status == ProjectStatus.active,
                            Project.repository_url != "",
                        )
                    ).all()
                )
                for project in projects:
                    if _delivery_status(project) not in _ACTIVE_STATES or not _retry_due(project, force=first_pass):
                        continue
                    try:
                        result = delivery.run_delivery(db, project, "system:mandatory-cloud-reconciler")
                        print(
                            f"[mandatory-cloud] {project.slug}: {result.get('status', 'unknown')} url={result.get('url', '')}",
                            flush=True,
                        )
                    except Exception as error:
                        # A single provider/project must never stop reconciliation for the others.
                        print(
                            f"[mandatory-cloud] {project.slug}: {type(error).__name__}: {error}",
                            flush=True,
                        )
            first_pass = False
        except Exception as error:
            print(f"[mandatory-cloud] reconciler error: {type(error).__name__}: {error}", flush=True)
            first_pass = False
        time.sleep(_RECONCILE_SECONDS)


def start() -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    threading.Thread(target=_run, name="mandatory-cloud-reconciler", daemon=True).start()


start()
