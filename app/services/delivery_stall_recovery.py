from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project, Task, TaskStatus
from app.services.audit import record


POLL_SECONDS = 20
STARTUP_GRACE_SECONDS = 12
QUEUED_STALL_SECONDS = 900
MAX_QUEUE_NUDGES_PER_ATTEMPT = 2
STALL_MARKER = "[delivery-stall-recovery:"
_STARTED = False
_LOCK = threading.Lock()
_GUARD_PATCHED = False


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _age_seconds(value: datetime | None) -> float:
    point = _aware(value)
    if point is None:
        return float("inf")
    return max(0.0, (datetime.now(timezone.utc) - point).total_seconds())


def _stall_count(task: Task) -> int:
    return str(task.prompt or "").count(STALL_MARKER)


def _delivery_state(project: Project) -> dict:
    try:
        config = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(config, dict):
        return {}
    state = config.get("delivery")
    return state if isinstance(state, dict) else {}


def _patch_exhausted_repair_lifecycle() -> None:
    """Prevent an exhausted delivery repair from spawning an endless new repair.

    The product guard historically created a fresh delivery-recovery task after the
    previous task reached MAX_SAFE_RETRIES. That reset the retry counter and could
    keep a mission at 100% in ``repairing/queued`` forever. The wrapper preserves
    the exhausted terminal task so the guard can expose ``repair_exhausted``.
    """
    global _GUARD_PATCHED
    if _GUARD_PATCHED:
        return

    from app.services import delivery_product_guard as guard

    current = guard._ensure_repair_task
    if getattr(current, "_devpilot_stall_lifecycle_fix", False):
        _GUARD_PATCHED = True
        return

    def bounded_ensure(db, project, reasons, paths, actor):
        existing = guard._latest_repair(db, project)
        if (
            existing
            and existing.status in {TaskStatus.failed, TaskStatus.blocked}
            and guard._retry_count(existing) >= guard.MAX_SAFE_RETRIES
        ):
            return existing, False
        return current(db, project, reasons, paths, actor)

    setattr(bounded_ensure, "_devpilot_stall_lifecycle_fix", True)
    guard._ensure_repair_task = bounded_ensure
    _GUARD_PATCHED = True


def recover_stalled_delivery_repairs_once() -> int:
    """Nudge stale queued final-delivery repairs and fail one attempt when necessary.

    A nudge is deliberately bounded. If the worker still does not claim the task,
    the current attempt is failed so the product guard can consume one of its
    existing bounded retries instead of displaying an eternal queued state.
    """
    recovered = 0
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        projects = list(
            db.scalars(select(Project).order_by(Project.created_at.desc()).limit(250)).all()
        )
        for project in projects:
            state = _delivery_state(project)
            if str(state.get("status") or "").lower() != "repairing":
                continue

            repair_id = str(state.get("repair_task_id") or "").strip()
            if not repair_id:
                continue
            task = db.get(Task, repair_id)
            if (
                task is None
                or task.project_id != project.id
                or task.workspace_id != project.workspace_id
                or task.source != "delivery-recovery"
                or task.status != TaskStatus.queued
                or _age_seconds(task.updated_at or task.created_at) < QUEUED_STALL_SECONDS
            ):
                continue

            nudge = _stall_count(task) + 1
            if nudge <= MAX_QUEUE_NUDGES_PER_ATTEMPT:
                task.prompt = (
                    f"{str(task.prompt or '').rstrip()}\n\n"
                    f"{STALL_MARKER}{nudge}]\n"
                    "A correção final permaneceu tempo demais na fila sem ser reivindicada. "
                    "Retome imediatamente esta mesma missão, preservando o trabalho existente e "
                    "publique o resultado no branch remoto exigido pela entrega."
                )[:100_000]
                task.priority = 100
                task.requires_approval = False
                task.approved_at = task.approved_at or now
                task.updated_at = now
                state["repair_task_status"] = "queued"
                state["stall_recovery"] = {
                    "status": "requeued",
                    "nudge": nudge,
                    "detected_at": now.isoformat(),
                    "reason": "delivery repair remained queued without worker claim",
                }
                config = json.loads(project.codex_config or "{}")
                config["delivery"] = state
                project.codex_config = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
                record(
                    db,
                    workspace_id=project.workspace_id,
                    project_id=project.id,
                    task_id=task.id,
                    actor="delivery-stall-recovery",
                    action="project.delivery_repair_stall_requeued",
                    outcome="queued",
                    details={"nudge": nudge, "stale_seconds": QUEUED_STALL_SECONDS},
                )
                db.commit()
                recovered += 1
                print(
                    f"[delivery-stall] requeued project={project.slug} task={task.id} nudge={nudge}",
                    flush=True,
                )
                continue

            # Do not leave the browser on an eternal queued state. Failing this
            # attempt lets the product guard perform its normal bounded retry with
            # fresh diagnostics; after MAX_SAFE_RETRIES it surfaces repair_exhausted.
            task.status = TaskStatus.failed
            task.updated_at = now
            state["repair_task_status"] = "failed"
            state["stall_recovery"] = {
                "status": "attempt_failed",
                "nudge": nudge - 1,
                "detected_at": now.isoformat(),
                "reason": "worker did not claim delivery repair after bounded queue recovery",
            }
            state["last_error"] = (
                "A correção automática ficou parada na fila. O DevPilot encerrou esta tentativa "
                "e vai usar a próxima tentativa segura automaticamente."
            )
            config = json.loads(project.codex_config or "{}")
            config["delivery"] = state
            project.codex_config = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
            record(
                db,
                workspace_id=project.workspace_id,
                project_id=project.id,
                task_id=task.id,
                actor="delivery-stall-recovery",
                action="project.delivery_repair_stall_failed",
                outcome="failed",
                details={
                    "nudges": MAX_QUEUE_NUDGES_PER_ATTEMPT,
                    "next": "bounded product-guard retry",
                },
            )
            db.commit()
            recovered += 1
            print(
                f"[delivery-stall] failed stale attempt project={project.slug} task={task.id}",
                flush=True,
            )
    return recovered


def _loop() -> None:
    time.sleep(STARTUP_GRACE_SECONDS)
    try:
        _patch_exhausted_repair_lifecycle()
    except Exception as error:
        print(
            f"[delivery-stall] lifecycle patch error={type(error).__name__}: {str(error)[:180]}",
            flush=True,
        )

    while True:
        try:
            recovered = recover_stalled_delivery_repairs_once()
            if recovered:
                print(f"[delivery-stall] recovered={recovered}", flush=True)
        except Exception as error:
            print(
                f"[delivery-stall] cycle error={type(error).__name__}: {str(error)[:180]}",
                flush=True,
            )
        time.sleep(POLL_SECONDS)


def start_delivery_stall_recovery() -> None:
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True
        threading.Thread(
            target=_loop,
            name="devpilot-delivery-stall-recovery",
            daemon=True,
        ).start()
