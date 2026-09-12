from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential
from app.services.vault import Vault


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
RunCommand = Callable[..., object]


def _repository_path(project: Project) -> Path:
    return get_settings().repositories_dir / SAFE_NAME.sub("-", project.slug)


def _git_environment(access_token: str | None = None) -> dict[str, str]:
    environment = {"GIT_TERMINAL_PROMPT": "0"}
    if not access_token:
        return environment
    encoded = base64.b64encode(f"x-access-token:{access_token}".encode()).decode()
    environment.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {encoded}",
        }
    )
    return environment


def _resolve_github_token(project: Project, run_command: RunCommand) -> str | None:
    """Return the first workspace credential that can actually read this repository.

    A project/organization binding is only a preference. Every enabled GitHub
    credential registered in the same workspace is eligible for failover, so a stale
    or missing organization link never forces the end user to authenticate GitHub.
    """
    with SessionLocal() as db:
        organization = db.get(Organization, project.organization_id) if project.organization_id else None

        credentials = list(
            db.scalars(
                select(ProviderCredential).where(
                    ProviderCredential.workspace_id == project.workspace_id,
                    ProviderCredential.provider == "github",
                    ProviderCredential.enabled.is_(True),
                )
            ).all()
        )
        preferred_credential_id = organization.credential_id if organization else None
        credentials.sort(key=lambda item: (item.id != preferred_credential_id, item.id))

        for credential in credentials:
            try:
                token = Vault().decrypt(credential.encrypted_secret).strip()
            except (TypeError, ValueError):
                continue
            if not token:
                continue

            probe = run_command(
                ["git", "ls-remote", project.repository_url, "HEAD"],
                timeout=45,
                env_overrides=_git_environment(token),
            )
            if getattr(probe, "returncode", 1) != 0:
                continue

            if organization and (
                organization.credential_id != credential.id or organization.last_sync_error
            ):
                organization.credential_id = credential.id
                organization.last_sync_error = ""
                db.commit()
            return token

    return None


def ensure_repository(project: Project, run_command: RunCommand) -> Path:
    """Prepare the checkout only after resolving a usable GitHub credential.

    For public repositories the unauthenticated clone succeeds naturally. For private
    repositories every active workspace credential is tested without exposing tokens
    in argv, logs or repository URLs. If no credential works, the clone is allowed to
    fail with the normal Git error so the recovery classifier can register an
    administrative repository-access problem without asking the end user for GitHub.
    """
    path = _repository_path(project)
    token = _resolve_github_token(project, run_command)
    git_env = _git_environment(token)

    if not path.exists():
        result = run_command(
            ["git", "clone", "--filter=blob:none", project.repository_url, str(path)],
            env_overrides=git_env,
        )
        if getattr(result, "returncode", 1):
            raise RuntimeError(getattr(result, "stderr", "").strip() or "Unable to clone repository")

    result = run_command(
        ["git", "fetch", "--prune", "origin"],
        cwd=path,
        env_overrides=git_env,
    )
    if getattr(result, "returncode", 1):
        raise RuntimeError(getattr(result, "stderr", "").strip() or "Unable to fetch repository")
    return path
