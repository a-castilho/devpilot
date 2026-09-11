from __future__ import annotations

import json
import threading
import time

_STARTED = False
_RECONCILE_SECONDS = 30
_INITIAL_DELAY_SECONDS = 15
# Delivery is mandatory and self-healing. A project that was blocked because a
# credential was missing, or failed while its repository/code was not ready, must
# be retried automatically after the external condition changes.
_ACTIVE_STATES = {"pending", "provisioning", "deploying", "blocked", "failed"}


def _delivery_status(project) -> str:
    try:
        config = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return "pending"
    if not isinstance(config, dict):
        return "pending"
    delivery = config.get("delivery")
    if not isinstance(delivery, dict):
        return "pending"
    return str(delivery.get("status") or "pending").strip().lower()


def _run() -> None:
    time.sleep(_INITIAL_DELAY_SECONDS)
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
                    if _delivery_status(project) not in _ACTIVE_STATES:
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
        except Exception as error:
            print(f"[mandatory-cloud] reconciler error: {type(error).__name__}: {error}", flush=True)
        time.sleep(_RECONCILE_SECONDS)


def start() -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    threading.Thread(target=_run, name="mandatory-cloud-reconciler", daemon=True).start()


start()
