from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.github_optional_org import github_credential_candidates, github_owner
from app.github_repository_selfheal import repair_github_project
from app.models import Project, ProviderCredential, Run, Task, TaskStatus
from app.services import executor
from app.services.audit import record
from app.services.recovery import AutoRecoveryService
from app.services.vault import Vault

_INTERVAL_SECONDS = 30
_STARTED = False
_LOCK = threading.Lock()
_LOG = logging.getLogger("devpilot.github_access_reconciler")
_RECOVERABLE_STATUSES = {TaskStatus.awaiting_approval, TaskStatus.blocked, TaskStatus.failed}


def _enabled() -> bool:
    values = (
        os.getenv("DEVPILOT_EXECUTION_ENABLED", ""),
        os.getenv("DEVPILOT_EMBEDDED_WORKER", ""),
    )
    return any(str(value).strip().lower() in {"1", "true", "yes", "on"} for value in values)


def _latest_run(db, task_id: str) -> Run | None:
    return db.scalar(
        select(Run)
        .where(Run.task_id == task_id)
        .order_by(Run.finished_at.desc())
        .limit(1)
    )


def _github_failure(db, task: Task) -> bool:
    if "[failure-category:github_auth]" in str(task.prompt or ""):
        return True
    run = _latest_run(db, task.id)
    if not run:
        return False
    text = f"{run.summary or ''}\n{run.logs or ''}".casefold()
    markers = (
        "github_auth",
        "github_access_denied",
        "write access to repository not granted",
        "repository not found",
        "could not read username for 'https://github.com'",
        "nenhuma possui acesso ao repositório",
    )
    return any(marker in text for marker in markers)


def _candidate_tasks(db, project: Project) -> list[Task]:
    tasks = list(
        db.scalars(
            select(Task)
            .where(
                Task.workspace_id == project.workspace_id,
                Task.project_id == project.id,
                Task.status.in_(tuple(_RECOVERABLE_STATUSES)),
            )
            .order_by(Task.updated_at.desc())
        ).all()
    )
    github_tasks = [task for task in tasks if _github_failure(db, task)]
    github_tasks.sort(
        key=lambda task: (
            0 if task.source == "failure-recovery" else 1,
            -(task.updated_at.timestamp() if task.updated_at else 0),
        )
    )
    return github_tasks


def _anonymous_access(repository_url: str) -> bool:
    try:
        result = executor.run(
            ["git", "ls-remote", repository_url, "HEAD"],
            timeout=30,
            env_overrides={"GIT_TERMINAL_PROMPT": "0"},
        )
    except Exception:
        return False
    return result.returncode == 0


def _prove_access(db, project: Project) -> tuple[bool, str]:
    if _anonymous_access(project.repository_url):
        return True, "anonymous git ls-remote succeeded"

    service = AutoRecoveryService()
    for credential in github_credential_candidates(db, project)[:8]:
        try:
            token = Vault().decrypt(credential.encrypted_secret)
        except ValueError:
            continue
        try:
            result = service._git_ls_remote(project.repository_url, token)
        except Exception:
            continue
        if result.returncode == 0:
            return True, f"authenticated git ls-remote succeeded with credential {credential.id}"
    return False, "no configured GitHub credential proved repository access"


def _resume_github_recovery(db, project: Project) -> int:
    """Repair repository state and resume exactly one blocked GitHub chain.

    We resume only the newest recovery task for a project (or the newest original
    GitHub-auth failure if there is no recovery task). This prevents old duplicate
    failures from being released as a burst while still unblocking the active flow.
    """
    candidates = _candidate_tasks(db, project)
    if not candidates:
        return 0

    repaired, repair_proof = repair_github_project(project)
    if repaired:
        try:
            db.refresh(project)
        except Exception:
            pass

    try:
        owner = github_owner(project.repository_url)
    except ValueError:
        return 0
    if not owner:
        return 0

    access_ok, access_proof = _prove_access(db, project)
    if not access_ok:
        _LOG.warning(
            "GitHub recovery still blocked project=%s repo=%s repair=%s access=%s",
            project.id,
            project.repository_url,
            repair_proof,
            access_proof,
        )
        return 0

    task = candidates[0]
    now = datetime.now(timezone.utc)
    task.status = TaskStatus.queued
    task.requires_approval = False
    task.approved_at = now
    task.updated_at = now
    record(
        db,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        task_id=task.id,
        actor="github-access-reconciler",
        action="failure_recovery.github_access_restored",
        outcome="queued",
        details={
            "automatic": True,
            "proof": access_proof,
            "repair_proof": repair_proof,
            "repository_owner": owner,
            "organization_id": project.organization_id,
            "organization_required": False,
            "resumed_source": task.source,
        },
    )
    _LOG.info("GitHub recovery resumed project=%s task=%s", project.id, task.id)
    return 1


def reconcile_once() -> int:
    resumed = 0
    with SessionLocal() as db:
        workspace_ids = list(
            db.scalars(
                select(ProviderCredential.workspace_id)
                .where(
                    ProviderCredential.provider.in_(("github", "cloud:github")),
                    ProviderCredential.enabled.is_(True),
                )
                .distinct()
            ).all()
        )
        for workspace_id in workspace_ids:
            projects = list(
                db.scalars(select(Project).where(Project.workspace_id == workspace_id)).all()
            )
            for project in projects:
                try:
                    resumed += _resume_github_recovery(db, project)
                except Exception:
                    _LOG.exception("GitHub reconciler failed project=%s", project.id)
        db.commit()
    return resumed


def _loop() -> None:
    while True:
        try:
            resumed = reconcile_once()
            if resumed:
                _LOG.info("GitHub reconciler resumed %s execution(s)", resumed)
        except Exception:
            _LOG.exception("GitHub reconciler iteration failed")
        time.sleep(_INTERVAL_SECONDS)


def start() -> None:
    global _STARTED
    if not _enabled():
        _LOG.info("GitHub reconciler disabled by execution settings")
        return
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True
        threading.Thread(target=_loop, name="devpilot-github-access-reconciler", daemon=True).start()
        _LOG.info("GitHub access reconciler started")


start()
