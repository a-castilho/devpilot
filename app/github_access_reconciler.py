from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential, Task, TaskStatus
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


def _metadata(item: ProviderCredential) -> dict:
    try:
        value = json.loads(item.models or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _github_owner(repository_url: str) -> str:
    parsed = urlparse(str(repository_url or ""))
    if str(parsed.hostname or "").lower() != "github.com":
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0].lower() if len(parts) >= 2 else ""


def _sync_cloud_credential(db, workspace_id: str) -> list[Organization]:
    cloud = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == "cloud:github",
            ProviderCredential.label == "cloud-admin",
            ProviderCredential.enabled.is_(True),
        )
    )
    organizations = list(
        db.scalars(
            select(Organization).where(
                Organization.workspace_id == workspace_id,
                Organization.provider == "github",
            )
        ).all()
    )
    if not cloud or not organizations:
        return organizations

    scope = str(_metadata(cloud).get("scope") or "").strip().lower()
    candidates = [org for org in organizations if str(org.external_login or "").strip().lower() == scope] if scope else organizations
    if not scope and len(candidates) != 1:
        return organizations

    for org in candidates:
        operational = db.get(ProviderCredential, org.credential_id) if org.credential_id else None
        if operational is None:
            operational = ProviderCredential(
                workspace_id=workspace_id,
                provider="github",
                label=f"GitHub org {org.external_login or org.slug}",
                encrypted_secret=cloud.encrypted_secret,
                enabled=True,
                models=json.dumps({"credential_source": "cloud-admin"}),
            )
            db.add(operational)
            db.flush()
            org.credential_id = operational.id
        elif operational.encrypted_secret != cloud.encrypted_secret or not operational.enabled:
            operational.encrypted_secret = cloud.encrypted_secret
            operational.enabled = True
            operational.models = json.dumps({"credential_source": "cloud-admin"})
        org.last_sync_error = ""
    return organizations


def _resume_github_recovery(db, project: Project, token: str) -> int:
    if not _github_owner(project.repository_url):
        return 0
    result = AutoRecoveryService()._git_ls_remote(project.repository_url, token)
    if result.returncode != 0:
        return 0

    now = datetime.now(timezone.utc)
    tasks = list(
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
    resumed = 0
    for task in tasks:
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
            details={"automatic": True, "proof": "git ls-remote succeeded"},
        )
        resumed += 1
    return resumed


def reconcile_once() -> int:
    resumed = 0
    with SessionLocal() as db:
        workspace_ids = list(
            db.scalars(
                select(ProviderCredential.workspace_id)
                .where(ProviderCredential.provider == "cloud:github", ProviderCredential.enabled.is_(True))
                .distinct()
            ).all()
        )
        for workspace_id in workspace_ids:
            organizations = _sync_cloud_credential(db, workspace_id)
            db.flush()
            for org in organizations:
                if not org.credential_id:
                    continue
                credential = db.get(ProviderCredential, org.credential_id)
                if not credential or not credential.enabled:
                    continue
                try:
                    token = Vault().decrypt(credential.encrypted_secret)
                except ValueError:
                    continue
                projects = list(
                    db.scalars(
                        select(Project).where(
                            Project.workspace_id == workspace_id,
                            Project.organization_id == org.id,
                        )
                    ).all()
                )
                for project in projects:
                    if _github_owner(project.repository_url) != str(org.external_login or "").strip().lower():
                        continue
                    resumed += _resume_github_recovery(db, project, token)
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
