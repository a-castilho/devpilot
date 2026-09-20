from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import product_delivery_routes as delivery
from app.delivery_url_recovery import install_delivery_url_recovery
from app.models import Project, Task, TaskStatus
from app.services.audit import record


_RECOVERABLE_STATUSES = {"blocked", "failed", "deploying", "provisioning"}
_RECOVERABLE_GATES = {"waiting_for_testable_url"}
_ACTIVE_DELAY_SECONDS = 15
_BLOCKED_DELAY_SECONDS = 60
_FAILURE_DELAY_SECONDS = 90
_SCAN_LIMIT = 200
_GAME_TASK_LIMIT = 80
_GAME_MARKER = "[DEVPILOT_BUILD_GAME_V1]"
_VERIFIER_MARKER = "[DEVPILOT_DELIVERY_VERIFIER_V1]"
_FIELD_RE = re.compile(r"^(?P<label>[A-Z_]+):\s*(?P<value>.+)$", re.MULTILINE)


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


def _prompt_field(prompt: object, label: str) -> str:
    wanted = label.strip().upper()
    for match in _FIELD_RE.finditer(str(prompt or "")):
        if match.group("label").strip().upper() == wanted:
            return match.group("value").strip()
    return ""


def _task_status(task: Task) -> str:
    value = getattr(task, "status", "")
    if hasattr(value, "value"):
        value = value.value
    return str(value or "").strip().lower()


def _final_gate_completed(db: Session, project_id: str) -> bool:
    """Return True only when phase 7 of the latest game mission was independently verified."""
    tasks = list(
        db.scalars(
            select(Task)
            .where(
                Task.project_id == project_id,
                Task.prompt.contains(_GAME_MARKER),
            )
            .order_by(Task.created_at.desc())
            .limit(_GAME_TASK_LIMIT)
        ).all()
    )
    if not tasks:
        return False

    latest_mission = _prompt_field(tasks[0].prompt, "PARTIDA")
    if not latest_mission:
        return False

    for task in tasks:
        if _prompt_field(task.prompt, "PARTIDA") != latest_mission:
            continue
        if _VERIFIER_MARKER not in str(task.prompt or ""):
            continue
        if _prompt_field(task.prompt, "FASE") != "7/7":
            continue
        if _task_status(task) == TaskStatus.completed.value:
            return True
    return False


def _eligible(
    db: Session,
    project: Project,
    state: dict,
    now: datetime,
) -> bool:
    status = str(state.get("status") or "pending").strip().lower()
    gate = str(state.get("delivery_gate") or "").strip().lower()

    if status == "ready" and gate != "waiting_for_testable_url":
        return False

    if status == "pending":
        if not _final_gate_completed(db, project.id):
            return False
    elif status not in _RECOVERABLE_STATUSES and gate not in _RECOVERABLE_GATES:
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


def process_one_pending_delivery(db: Session, *, now: datetime | None = None) -> bool:
    """Advance one final delivery without depending on an open browser tab.

    A completed phase-7 verifier starts a still-pending delivery. Once started,
    recoverable states are retried with persisted backoff. The delivery state
    machine remains idempotent and owns provider reuse.
    """
    current_time = (now or _utcnow()).astimezone(timezone.utc)
    projects = list(
        db.scalars(
            select(Project)
            .where(
                Project.repository_url.is_not(None),
                Project.repository_url != "",
            )
            .order_by(Project.id.asc())
            .limit(_SCAN_LIMIT)
        ).all()
    )

    for project in projects:
        state = delivery.initial_delivery(project)
        if not _eligible(db, project, state, current_time):
            continue

        previous_status = str(state.get("status") or "pending").strip().lower()
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
                    details={
                        "url": result.get("url"),
                        "previous_status": previous_status,
                    },
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
