from __future__ import annotations

import os
from collections.abc import Callable

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential
from app.services.vault import Vault


CLOUD_GITHUB_PROVIDER = "cloud:github"
CLOUD_GITHUB_LABEL = "cloud-admin"
RUNTIME_GITHUB_KEYS = ("DEVPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")


def _decrypt(credential: ProviderCredential | None) -> str:
    if not credential or not credential.enabled:
        return ""
    try:
        return Vault().decrypt(credential.encrypted_secret).strip()
    except ValueError as error:
        raise RuntimeError("GitHub credential cannot be decrypted") from error


def _organization_token(db, project: Project) -> str:
    if not project.organization_id:
        return ""
    organization = db.scalar(select(Organization).where(Organization.id == project.organization_id))
    if not organization or not organization.credential_id:
        return ""
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == organization.credential_id,
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
    """Resolve GitHub auth once, preferring project/org scope then managed cloud then runtime.

    Secrets stay server-side and are only returned to the executor process that prepares Git's
    in-memory environment. Nothing is persisted into repository remotes or command arguments.
    """
    with SessionLocal() as db:
        token = _organization_token(db, project)
        if token:
            return token
        token = _managed_cloud_token(db, project)
        if token:
            return token
    return _runtime_token()


def install(executor_module) -> None:
    original: Callable[[Project], dict[str, str]] = executor_module.git_environment
    if getattr(original, "__devpilot_managed_github_bridge__", False):
        return

    def bridged_git_environment(project: Project) -> dict[str, str]:
        environment = original(project)
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
