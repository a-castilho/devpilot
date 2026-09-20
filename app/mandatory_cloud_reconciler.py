from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

_STARTED = False
_RECONCILE_SECONDS = 30
_INITIAL_DELAY_SECONDS = 15
_FAILED_RETRY_SECONDS = 300
# Delivery is mandatory and self-healing. waiting_code/repairing are active states:
# code materialization and product repair must keep advancing without a browser.
_ACTIVE_STATES = {"pending", "provisioning", "deploying", "waiting_code", "repairing", "blocked", "failed"}


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


def _result_diagnostics(result: dict) -> str:
    def clean(value: object, limit: int = 180) -> str:
        return " ".join(str(value or "").split())[:limit]

    blocked = result.get("blocked_providers")
    blocked_text = ",".join(clean(item, 40) for item in blocked) if isinstance(blocked, list) else ""
    parts = [
        f"blocked_providers={blocked_text}",
        f"failed_provider={clean(result.get('failed_provider'), 60)}",
        f"gate={clean(result.get('delivery_gate'), 80)}",
        f"repair={clean(result.get('repair_task_status'), 80)}",
        f"waiting_for={clean(result.get('waiting_for'), 80)}",
        f"error={clean(result.get('last_error'))}",
    ]
    return " ".join(parts)[:500]


def _run() -> None:
    """Compatibility loop delegated to the authoritative delivery reconciler.

    This module used to call providers independently, including pending projects.
    Delegating keeps legacy startup wiring intact while guaranteeing that all
    provider writes use the same Gate 7/7 eligibility check and persisted lease.
    """
    time.sleep(_INITIAL_DELAY_SECONDS)
    while True:
        try:
            from app.delivery_url_recovery import _reconcile_once

            processed = _reconcile_once()
            if processed:
                print(f"[mandatory-cloud] delegated processed={processed}", flush=True)
        except Exception as error:
            print(
                f"[mandatory-cloud] delegated reconciler error: {type(error).__name__}: {error}",
                flush=True,
            )
        time.sleep(_RECONCILE_SECONDS)

def start() -> None:
    global _STARTED
    if _STARTED:
        return
    _STARTED = True
    threading.Thread(target=_run, name="mandatory-cloud-reconciler", daemon=True).start()


start()
