from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.github_optional_org import github_credential_candidates, github_owner
from app.models import Project, ProviderCredential, Task, TaskStatus
from app.services.audit import record
from app.services.recovery import AutoRecoveryService
from app.services.vault import Vault

_INTERVAL_SECONDS = 30
_STARTED = False
_LOCK = threading.Lock()


def _enabled() -> bool:
    values = (
        os.getenv("DEVPILOT_EXECUTION_ENABLED", ""),
        os.getenv("DEVPILOT_EMBEDDED_WORKER", ""),
    )
    return any(str(value).strip().lower() in {"1", "true", "yes", "on"} for value in values)


def _resume_github_recovery(db, project: Project) -> int:
    """Validate real repository access and resume blocked recovery tasks.

    Project.organization_id is intentionally optional. The repository owner and
    workspace credentials are enough to prove access. Organization only affects
    credential priority through github_credential_candidates().
    """
    try:
        owner = github_owner(project.repository_url)
    except ValueError:
        return 0
    if not owner:
        return 0

    pending = list(
        db.scalars(
            select(Task).where(
                Task.workspace_id == project.workspace_id,
                Task.project_id == project.id,
                Task.source == "failure-recovery",
                Task.status == TaskStatus.awaiting_approval,
                Task.requires_approval.is_(True),
                Task.prompt.contains("[failure-category:github_auth]"),
            )
        ).all()
    )
    if not pending:
        return 0

    service = AutoRecoveryService()
    access_proof = ""

    # A public repository can recover without any credential at all.
    try:
        anonymous = service._git_ls_remote(project.repository_url, "")
        if anonymous.returncode == 0:
            access_proof = "git ls-remote succeeded without organization requirement"
    except Exception:
        pass

    if not access_proof:
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
                access_proof = f"git ls-remote succeeded for repository owner {owner}"
                break

    if not access_proof:
        return 0

    now = datetime.now(timezone.utc)
    resumed = 0
    for task in pending:
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
                "repository_owner": owner,
                "organization_id": project.organization_id,
                "organization_required": False,
            },
        )
        resumed += 1
    return resumed


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
                db.scalars(
                    select(Project).where(Project.workspace_id == workspace_id)
                ).all()
            )
            for project in projects:
                resumed += _resume_github_recovery(db, project)
        db.commit()
    return resumed


def _loop() -> None:
    while True:
        try:
            reconcile_once()
        except Exception:
            pass
        time.sleep(_INTERVAL_SECONDS)


def start() -> None:
    global _STARTED
    if not _enabled():
        return
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True
        threading.Thread(target=_loop, name="devpilot-github-access-reconciler", daemon=True).start()


start()
