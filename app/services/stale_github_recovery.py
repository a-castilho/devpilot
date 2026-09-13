from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.config import get_settings
from app.db import SessionLocal
from app.models import Project, Run, Task, TaskStatus
from app.services.github_access_bridge import resolve_github_access


_POLL_SECONDS = 20
_MAX_CANDIDATES = 200
_MAX_GITHUB_FAILURE_RUNS = 3
_STARTED = False
_START_LOCK = threading.Lock()
_STOP = threading.Event()


def _run_is_github_auth(run: Run) -> bool:
    text = f"{run.summary or ''}\n{run.logs or ''}".lower()
    if any(
        marker in text
        for marker in (
            "github_access_denied",
            "github_auth",
            "could not read username for 'https://github.com'",
            'could not read username for "https://github.com',
            "terminal prompts disabled",
        )
    ):
        return True

    try:
        payload = json.loads(run.logs or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False

    failure = payload.get("failure_context")
    if isinstance(failure, dict) and str(failure.get("category") or "").lower() == "github_auth":
        return True
    healing = payload.get("self_healing")
    return isinstance(healing, dict) and str(healing.get("category") or "").lower() == "github_auth"


def _repository_ready_for_execution(project: Project) -> tuple[bool, str]:
    try:
        resolution = resolve_github_access(project)
    except Exception as error:
        print(f"[github-recovery] remote preflight error project={project.id}: {error}", flush=True)
        resolution = None

    if resolution is not None and resolution.ok:
        return True, resolution.credential_id or "remote"

    # GitHub is a delivery concern for DevPilot-managed projects. If every remote
    # recovery route is exhausted, keep development moving in the isolated local Git
    # workspace and let delivery reconcile/publish the remote later.
    try:
        from app.services.managed_local_repository import ensure_managed_local_repository

        local = ensure_managed_local_repository(project)
    except Exception as error:
        print(f"[github-recovery] local fallback error project={project.id}: {error}", flush=True)
        return False, ""
    if local is None:
        return False, ""
    return True, "managed-local"


def recover_stale_github_failures_once() -> int:
    """Requeue GitHub-auth failures once execution has a valid repository workspace."""
    recovered = 0
    with SessionLocal() as db:
        tasks = list(
            db.scalars(
                select(Task)
                .where(
                    Task.status.in_([TaskStatus.failed, TaskStatus.blocked]),
                    Task.source != "failure-recovery",
                )
                .order_by(Task.updated_at.desc())
                .limit(_MAX_CANDIDATES)
            ).all()
        )

        for task in tasks:
            runs = list(
                db.scalars(
                    select(Run)
                    .where(Run.task_id == task.id)
                    .order_by(Run.started_at.desc())
                    .limit(_MAX_GITHUB_FAILURE_RUNS + 1)
                ).all()
            )
            github_runs = [run for run in runs if _run_is_github_auth(run)]
            if not github_runs or len(github_runs) > _MAX_GITHUB_FAILURE_RUNS:
                continue

            project = db.get(Project, task.project_id)
            if project is None:
                continue

            ready, strategy = _repository_ready_for_execution(project)
            if not ready:
                continue

            now = datetime.now(timezone.utc)
            changed = db.execute(
                update(Task)
                .where(
                    Task.id == task.id,
                    Task.status.in_([TaskStatus.failed, TaskStatus.blocked]),
                )
                .values(
                    status=TaskStatus.queued,
                    requires_approval=False,
                    approved_at=now,
                    updated_at=now,
                )
            )
            if not changed.rowcount:
                continue

            db.commit()
            recovered += 1
            print(
                f"[github-recovery] requeued stale task={task.id} project={project.id} strategy={strategy}",
                flush=True,
            )

    return recovered


def _loop() -> None:
    while not _STOP.is_set():
        try:
            recover_stale_github_failures_once()
        except Exception as error:
            print(f"[github-recovery] loop error: {error}", flush=True)
        _STOP.wait(_POLL_SECONDS)


def start_stale_github_recovery() -> None:
    global _STARTED
    if not get_settings().execution_enabled:
        return
    with _START_LOCK:
        if _STARTED:
            return
        _STARTED = True
        threading.Thread(
            target=_loop,
            name="devpilot-stale-github-recovery",
            daemon=True,
        ).start()
