from __future__ import annotations

import os
import re
from collections.abc import Callable

from sqlalchemy import or_, select

from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential
from app.services.vault import Vault


CLOUD_GITHUB_PROVIDER = "cloud:github"
CLOUD_GITHUB_LABEL = "cloud-admin"
RUNTIME_GITHUB_KEYS = ("DEVPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
_GITHUB_OWNER_RE = re.compile(r"^(?:https?://|git@)github\.com(?:/|:)([^/]+)/[^/]+?(?:\.git)?$", re.IGNORECASE)


def _decrypt(credential: ProviderCredential | None) -> str:
    if not credential or not credential.enabled:
        return ""
    try:
        return Vault().decrypt(credential.encrypted_secret).strip()
    except ValueError as error:
        raise RuntimeError("GitHub credential cannot be decrypted") from error


def _repository_owner(project: Project) -> str:
    value = str(project.repository_url or "").strip().rstrip("/")
    match = _GITHUB_OWNER_RE.match(value)
    return match.group(1).strip() if match else ""


def _organization_for_project(db, project: Project) -> Organization | None:
    if project.organization_id:
        return db.scalar(
            select(Organization).where(
                Organization.id == project.organization_id,
                Organization.workspace_id == project.workspace_id,
                Organization.provider == "github",
            )
        )

    owner = _repository_owner(project)
    if not owner:
        return None
    return db.scalar(
        select(Organization)
        .where(
            Organization.workspace_id == project.workspace_id,
            Organization.provider == "github",
            or_(
                Organization.external_login.ilike(owner),
                Organization.slug.ilike(owner),
            ),
        )
        .order_by(Organization.created_at.desc())
        .limit(1)
    )


def _organization_token(db, project: Project) -> str:
    organization = _organization_for_project(db, project)
    if not organization or not organization.credential_id:
        return ""
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == organization.credential_id,
            ProviderCredential.workspace_id == project.workspace_id,
            ProviderCredential.provider == "github",
            ProviderCredential.enabled.is_(True),
        )
    )
    return _decrypt(credential)


def _managed_cloud_token(db, project: Project) -> str:
    credential = db.scalar(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == project.workspace_id,
            ProviderCredential.provider == CLOUD_GITHUB_PROVIDER,
            ProviderCredential.label == CLOUD_GITHUB_LABEL,
            ProviderCredential.enabled.is_(True),
        )
        .order_by(ProviderCredential.created_at.desc())
        .limit(1)
    )
    return _decrypt(credential)


def _runtime_token() -> str:
    for key in RUNTIME_GITHUB_KEYS:
        value = str(os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def github_token_for_project(project: Project) -> str:
    """Resolve GitHub auth from the project owner, managed cloud or runtime.

    The repository owner is used as a fallback when an older project has no explicit
    organization_id. Secrets stay server-side and are only injected into Git's in-memory
    environment; they are never persisted into repository remotes or command arguments.
    """
    with SessionLocal() as db:
        token = _organization_token(db, project)
        if token:
            return token
        token = _managed_cloud_token(db, project)
        if token:
            return token
    return _runtime_token()


def _attach_repository_owner(project: Project) -> None:
    """Backfill the in-memory organization link for legacy projects before execution.

    Some execution/recovery guards require project.organization_id. Older synchronized
    projects can have a valid GitHub repository and workspace credential while this FK is
    empty. Resolve the repository owner and attach the matching organization so every guard
    and the Git transport observe the same current authorization state.
    """
    if project.organization_id or not _repository_owner(project):
        return
    with SessionLocal() as db:
        organization = _organization_for_project(db, project)
        if organization and organization.credential_id:
            credential = db.scalar(
                select(ProviderCredential).where(
                    ProviderCredential.id == organization.credential_id,
                    ProviderCredential.workspace_id == project.workspace_id,
                    ProviderCredential.provider == "github",
                    ProviderCredential.enabled.is_(True),
                )
            )
            if credential:
                project.organization_id = organization.id


def install(executor_module) -> None:
    original_git_environment: Callable[[Project], dict[str, str]] = executor_module.git_environment
    if not getattr(original_git_environment, "__devpilot_managed_github_bridge__", False):
        def bridged_git_environment(project: Project) -> dict[str, str]:
            environment = original_git_environment(project)
            if environment.get("GIT_CONFIG_VALUE_0"):
                return environment

            token = github_token_for_project(project)
            if not token:
                return environment

            environment.update(
                {
                    "GIT_TERMINAL_PROMPT": "0",
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "http.extraHeader",
                    "GIT_CONFIG_VALUE_0": executor_module.github_basic_authorization(token),
                }
            )
            return environment

        bridged_git_environment.__devpilot_managed_github_bridge__ = True
        executor_module.git_environment = bridged_git_environment

    original_execute_task = executor_module.execute_task
    if not getattr(original_execute_task, "__devpilot_github_owner_bridge__", False):
        def bridged_execute_task(project, task):
            _attach_repository_owner(project)
            return original_execute_task(project, task)

        bridged_execute_task.__devpilot_github_owner_bridge__ = True
        executor_module.execute_task = bridged_execute_task
