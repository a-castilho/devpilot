from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential, TaskStatus
from app.services.vault import Vault


_GITHUB_HOST_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com[/:]([^/]+)/([^/#?]+)", re.I)
_MAX_CREDENTIAL_CANDIDATES = 20
_MANAGED_GITHUB_OWNER = "a-castilho"
_MANAGED_REPOSITORY_MODES = {"automatic", "deferred"}


@dataclass(frozen=True)
class GitHubAccessResolution:
    ok: bool
    environment: dict[str, str]
    credential_id: str = ""
    organization_id: str = ""
    message: str = ""


def _repository_owner(repository_url: str) -> str:
    value = str(repository_url or "").strip()
    if value.startswith("git@github.com:"):
        path = value.split(":", 1)[1]
        return path.split("/", 1)[0].strip().lower()
    match = _GITHUB_HOST_RE.search(value)
    return match.group(1).strip().lower() if match else ""


def _git_environment(token: str) -> dict[str, str]:
    encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {encoded}",
    }


def _probe(repository_url: str, token: str) -> bool:
    env = os.environ.copy()
    env.update(_git_environment(token))
    try:
        result = subprocess.run(
            ["git", "ls-remote", repository_url, "HEAD"],
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _project_config(project: Project) -> dict:
    raw = project.codex_config
    if isinstance(raw, dict):
        return dict(raw)
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, dict) else {}


def _managed_repository(project: Project) -> bool:
    config = _project_config(project)
    mode = str(config.get("repository_mode") or "").strip().lower()
    if mode in _MANAGED_REPOSITORY_MODES:
        return True
    if bool(config.get("repository_pending")):
        return True
    return _repository_owner(str(project.repository_url or "")) == _MANAGED_GITHUB_OWNER


def _repair_managed_repository(project: Project) -> GitHubAccessResolution | None:
    """Recreate/rebind a DevPilot-managed repository before asking a human for help.

    A project created by DevPilot is allowed to recover its own repository inside the
    administrative organization. Explicit third-party repositories are never replaced.
    Every active GitHub credential in the workspace is tried, because a stale
    organization->credential link must not turn into an end-user intervention.
    """
    if not _managed_repository(project):
        return None

    from app.services.github_provisioning import create_github_repository

    with SessionLocal() as db:
        db_project = db.scalar(
            select(Project).where(
                Project.id == project.id,
                Project.workspace_id == project.workspace_id,
            )
        )
        if db_project is None:
            return None

        organization = db.scalar(
            select(Organization).where(
                Organization.workspace_id == project.workspace_id,
                Organization.provider == "github",
                Organization.external_login.ilike(_MANAGED_GITHUB_OWNER),
            )
        )
        if organization is None:
            return None

        credentials = list(
            db.scalars(
                select(ProviderCredential).where(
                    ProviderCredential.workspace_id == project.workspace_id,
                    ProviderCredential.provider == "github",
                    ProviderCredential.enabled.is_(True),
                )
            ).all()
        )
        preferred_id = str(organization.credential_id or "")
        credentials.sort(key=lambda item: (str(item.id) != preferred_id, str(item.created_at or "")))

        for credential in credentials[:_MAX_CREDENTIAL_CANDIDATES]:
            try:
                token = Vault().decrypt(credential.encrypted_secret).strip()
            except (TypeError, ValueError):
                continue
            if not token:
                continue

            try:
                remote = create_github_repository(
                    _MANAGED_GITHUB_OWNER,
                    db_project.slug,
                    db_project.description,
                    token,
                )
            except Exception:
                continue

            repository_url = str(remote.get("clone_url") or "").strip()
            if not repository_url or not _probe(repository_url, token):
                continue

            db_project.organization_id = organization.id
            db_project.repository_url = repository_url
            db_project.default_branch = str(remote.get("default_branch") or "main")
            config = _project_config(db_project)
            config["repository_pending"] = False
            config["repository_mode"] = "automatic"
            config["repository_provision_state"] = "ready"
            config["repository_recovered_automatically"] = True
            db_project.codex_config = json.dumps(config)
            organization.credential_id = credential.id
            organization.last_sync_error = ""
            db.commit()

            # Keep the detached Project instance used by the worker coherent for the
            # same attempt. The next retry must clone the repaired URL immediately,
            # not wait for a fresh ORM load.
            project.organization_id = organization.id
            project.repository_url = repository_url
            project.default_branch = db_project.default_branch
            project.codex_config = db_project.codex_config

            return GitHubAccessResolution(
                True,
                _git_environment(token),
                credential_id=str(credential.id),
                organization_id=str(organization.id),
                message=(
                    "O DevPilot reprovisionou automaticamente o repositório gerenciado, "
                    "reparou o vínculo GitHub e validou o acesso antes de retomar a tarefa."
                ),
            )

    return None


def resolve_github_access(project: Project, *, persist: bool = True) -> GitHubAccessResolution:
    """Resolve a credential by proving access to the exact repository.

    Project and organization links are hints, not requirements. The resolver searches
    active GitHub credentials in the same workspace, validates each one with
    ``git ls-remote`` and repairs stale links when possible. For DevPilot-managed
    projects it can also reprovision/rebind the repository automatically. Secrets never
    leave the backend and the end user is never responsible for repository authentication.
    """
    repository_url = str(project.repository_url or "").strip()
    if not repository_url:
        repaired = _repair_managed_repository(project)
        if repaired:
            return repaired
        return GitHubAccessResolution(
            False,
            {"GIT_TERMINAL_PROMPT": "0"},
            message="Projeto sem repositório GitHub vinculado e sem recuperação administrativa disponível.",
        )

    owner = _repository_owner(repository_url)
    with SessionLocal() as db:
        db_project = db.scalar(
            select(Project).where(
                Project.id == project.id,
                Project.workspace_id == project.workspace_id,
            )
        )
        effective_project = db_project or project

        organizations = list(
            db.scalars(
                select(Organization).where(
                    Organization.workspace_id == project.workspace_id,
                    Organization.provider == "github",
                )
            ).all()
        )
        by_id = {str(item.id): item for item in organizations}
        owner_org = next(
            (
                item
                for item in organizations
                if str(item.external_login or "").strip().lower() == owner
            ),
            None,
        )
        current_org = by_id.get(str(effective_project.organization_id or ""))

        credentials = list(
            db.scalars(
                select(ProviderCredential).where(
                    ProviderCredential.workspace_id == project.workspace_id,
                    ProviderCredential.provider == "github",
                    ProviderCredential.enabled.is_(True),
                )
            ).all()
        )
        priority_ids: list[str] = []
        for organization in (current_org, owner_org):
            credential_id = str(getattr(organization, "credential_id", "") or "")
            if credential_id and credential_id not in priority_ids:
                priority_ids.append(credential_id)
        credentials.sort(
            key=lambda item: (
                priority_ids.index(str(item.id))
                if str(item.id) in priority_ids
                else len(priority_ids),
                str(item.created_at or ""),
            )
        )

        for credential in credentials[:_MAX_CREDENTIAL_CANDIDATES]:
            try:
                token = Vault().decrypt(credential.encrypted_secret).strip()
            except (TypeError, ValueError):
                continue
            if not token or not _probe(repository_url, token):
                continue

            organization = owner_org or current_org
            if persist and organization is not None:
                changed = False
                if str(organization.credential_id or "") != str(credential.id):
                    organization.credential_id = credential.id
                    organization.last_sync_error = ""
                    changed = True
                if db_project is not None and str(db_project.organization_id or "") != str(organization.id):
                    db_project.organization_id = organization.id
                    changed = True
                if changed:
                    db.commit()

            return GitHubAccessResolution(
                True,
                _git_environment(token),
                credential_id=str(credential.id),
                organization_id=str(organization.id) if organization else "",
                message="Credencial GitHub cadastrada no DevPilot validada para o repositório.",
            )

    repaired = _repair_managed_repository(project)
    if repaired:
        return repaired

    return GitHubAccessResolution(
        False,
        {"GIT_TERMINAL_PROMPT": "0"},
        message=(
            "As credenciais GitHub cadastradas foram testadas, o reparo automático de "
            "repositório gerenciado também foi tentado e nenhuma rota administrativa válida foi encontrada."
        ),
    )


def install_github_access_bridge() -> None:
    """Install repository-specific resolution in every Git checkout and recovery flow."""
    from app.services import executor
    from app.services import failure_recovery
    from app.services.github_checkout import ensure_repository as ensure_authenticated_repository
    from app.services.recovery import AutoRecoveryService, RecoveryDecision

    # The executor historically had its own clone/fetch implementation. That allowed
    # some code paths to bypass the repository credential resolver and fall back to an
    # anonymous HTTPS clone, producing `could not read Username` in non-interactive
    # workers. Route the canonical executor entry point through the authenticated
    # checkout service so every caller (worker, RAG, Git reader and recovery flow)
    # gets the same credential failover behavior.
    if not getattr(executor.ensure_repository, "_devpilot_repository_access_bridge", False):
        def ensure_repository(project: Project):
            return ensure_authenticated_repository(project, executor.run)

        setattr(ensure_repository, "_devpilot_repository_access_bridge", True)
        executor.ensure_repository = ensure_repository

    if not getattr(executor.git_environment, "_devpilot_repository_access_bridge", False):
        def git_environment(project: Project) -> dict[str, str]:
            resolution = resolve_github_access(project)
            if resolution.ok:
                return resolution.environment
            return {"GIT_TERMINAL_PROMPT": "0"}

        setattr(git_environment, "_devpilot_repository_access_bridge", True)
        executor.git_environment = git_environment

    current = AutoRecoveryService._recover_github_access
    if not getattr(current, "_devpilot_repository_access_bridge", False):
        def recover_github_access(self, project: Project, execution_attempt: int):
            resolution = resolve_github_access(project)
            if resolution.ok:
                return RecoveryDecision(
                    "github_auth",
                    "resolved",
                    resolution.message,
                    execution_attempt < self.MAX_ATTEMPTS,
                    False,
                    "repository_credential_rebind_or_reprovision",
                    [{
                        "state": "credential_validated",
                        "attempt": execution_attempt,
                        "message": resolution.message,
                    }],
                )
            return RecoveryDecision(
                "github_auth",
                "needs_attention",
                resolution.message,
                False,
                False,
                "github_credentials_and_managed_repair_exhausted",
                [{
                    "state": "credential_rejected",
                    "attempt": execution_attempt,
                    "message": resolution.message,
                }],
            )

        setattr(recover_github_access, "_devpilot_repository_access_bridge", True)
        AutoRecoveryService._recover_github_access = recover_github_access

    original_ensure = failure_recovery.ensure_failure_recovery_task
    if getattr(original_ensure, "_devpilot_repository_access_bridge", False):
        return

    def ensure_failure_recovery_task(db, *, original_task, run, failure, actor="worker"):
        recovery = original_ensure(
            db,
            original_task=original_task,
            run=run,
            failure=failure,
            actor=actor,
        )
        if not recovery:
            return recovery
        if str(failure.get("category") or "").lower() != "github_auth":
            return recovery

        project = db.get(Project, original_task.project_id)
        if not project:
            return recovery

        resolution = resolve_github_access(project)
        now = datetime.now(timezone.utc)

        if resolution.ok:
            recovery.requires_approval = False
            recovery.approved_at = recovery.approved_at or now
            recovery.status = TaskStatus.queued
            recovery.updated_at = now
            db.flush()
            return recovery

        # Repository authentication stays an administrative system dependency. The AI
        # recovery bridge gets a final chance to diagnose it; an end-user approval gate
        # is never fabricated here.
        recovery.requires_approval = False
        recovery.approved_at = recovery.approved_at or now
        if recovery.status == TaskStatus.awaiting_approval:
            recovery.status = TaskStatus.blocked
        recovery.updated_at = now
        db.flush()
        return recovery

    setattr(ensure_failure_recovery_task, "_devpilot_repository_access_bridge", True)
    failure_recovery.ensure_failure_recovery_task = ensure_failure_recovery_task
