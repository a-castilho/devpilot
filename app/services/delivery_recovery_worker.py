from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import product_delivery_routes as delivery
from app.delivery_url_recovery import install_delivery_url_recovery
from app.models import Project
from app.services.audit import record


_RECOVERABLE_STATUSES = {"blocked", "failed", "deploying", "provisioning"}
_RECOVERABLE_GATES = {"waiting_for_testable_url"}
_ACTIVE_DELAY_SECONDS = 15
_BLOCKED_DELAY_SECONDS = 60
_FAILURE_DELAY_SECONDS = 90
_SCAN_LIMIT = 200


install_delivery_url_recovery()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: object) -> datetime | None:
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


def _eligible(state: dict, now: datetime) -> bool:
    status = str(state.get("status") or "").strip().lower()
    gate = str(state.get("delivery_gate") or "").strip().lower()
    if status not in _RECOVERABLE_STATUSES and gate not in _RECOVERABLE_GATES:
        return False
    next_at = _parse_timestamp(state.get("recovery_next_at"))
    return next_at is None or next_at <= now


def _next_delay(status: str) -> int:
    normalized = str(status or "").strip().lower()
    if normalized == "blocked":
        return _BLOCKED_DELAY_SECONDS
    if normalized == "failed":
        return _FAILURE_DELAY_SECONDS
    return _ACTIVE_DELAY_SECONDS


def _persist_schedule(
    db: Session,
    project: Project,
    state: dict,
    *,
    now: datetime,
    delay_seconds: int,
    error: str = "",
) -> None:
    state["recovery_last_attempt_at"] = now.isoformat()
    state["recovery_next_at"] = (now + timedelta(seconds=max(1, delay_seconds))).isoformat()
    state["recovery_owner"] = "worker"
    if error:
        state["recovery_last_error"] = " ".join(error.split())[:300]
    elif "recovery_last_error" in state:
        state["recovery_last_error"] = ""
    delivery.save_delivery(db, project, state)
    db.commit()


def process_one_pending_delivery(db: Session, *, now: datetime | None = None) -> bool:
    """Advance one recoverable delivery without depending on an open browser tab.

    The delivery state machine is idempotent and remains responsible for provider
    reuse. This worker only gives pending/blocked delivery states a durable owner
    and a bounded retry cadence.
    """
    current_time = (now or _utcnow()).astimezone(timezone.utc)
    projects = list(
        db.scalars(
            select(Project)
            .where(Project.repository_url.is_not(None))
            .order_by(Project.id.asc())
            .limit(_SCAN_LIMIT)
        ).all()
    )

    for project in projects:
        state = delivery.initial_delivery(project)
        if not _eligible(state, current_time):
            continue

        previous_status = str(state.get("status") or "").strip().lower()
        _persist_schedule(
            db,
            project,
            state,
            now=current_time,
            delay_seconds=_next_delay(previous_status),
        )

        try:
            result = delivery.run_delivery(db, project, "system:delivery-recovery")
            result_status = str(result.get("status") or "").strip().lower()
            if result_status == "ready" and str(result.get("url") or "").startswith("https://"):
                result["recovery_next_at"] = ""
                result["recovery_owner"] = "worker"
                result["recovery_last_error"] = ""
                delivery.save_delivery(db, project, result)
                record(
                    db,
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    actor="system:delivery-recovery",
                    action="project.delivery_recovery_completed",
                    outcome="success",
                    details={"url": result.get("url"), "previous_status": previous_status},
                )
                db.commit()
                return True

            _persist_schedule(
                db,
                project,
                result,
                now=current_time,
                delay_seconds=_next_delay(result_status),
            )
            return True
        except Exception as error:  # provider/network failures must not kill the worker loop
            db.rollback()
            refreshed = db.get(Project, project.id)
            if refreshed is None:
                return True
            failed_state = delivery.initial_delivery(refreshed)
            _persist_schedule(
                db,
                refreshed,
                failed_state,
                now=current_time,
                delay_seconds=_FAILURE_DELAY_SECONDS,
                error=str(error),
            )
            record(
                db,
                workspace_id=refreshed.workspace_id,
                project_id=refreshed.id,
                actor="system:delivery-recovery",
                action="project.delivery_recovery_retry_scheduled",
                outcome="pending",
                details={"error": " ".join(str(error).split())[:180]},
            )
            db.commit()
            return True

    return False
