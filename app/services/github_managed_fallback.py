from __future__ import annotations

import json

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project, ProviderCredential
from app.services.vault import Vault


_MAX_CREDENTIALS = 20
_MAX_NAME_ATTEMPTS = 20


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot/1.0",
    }


def _candidate(base: str, attempt: int) -> str:
    if attempt <= 1:
        return base
    suffix = f"-{attempt}"
    return f"{base[:100-len(suffix)].rstrip('-')}{suffix}"


def _authenticated_login(token: str) -> str:
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=_headers(token)) as client:
            response = client.get("https://api.github.com/user")
        if response.status_code != 200:
            return ""
        payload = response.json()
    except Exception:
        return ""
    return str(payload.get("login") or "").strip() if isinstance(payload, dict) else ""


def _create_personal_repository(token: str, *, login: str, project: Project) -> tuple[dict, str] | None:
    from app.services.github_provisioning import bootstrap_repository
    from app.services.organizations import normalize_github_repository

    base = str(project.slug or "project").strip() or "project"
    description = str(project.description or "").strip()

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=_headers(token)) as client:
        for attempt in range(1, _MAX_NAME_ATTEMPTS + 1):
            name = _candidate(base, attempt)
            response = client.post(
                "https://api.github.com/user/repos",
                json={
                    "name": name,
                    "description": description,
                    "private": True,
                    "auto_init": True,
                },
            )
            if response.status_code == 422:
                continue
            if response.status_code not in {200, 201}:
                return None
            try:
                remote = normalize_github_repository(response.json())
            except Exception:
                return None

            try:
                bootstrap_repository(
                    login,
                    name,
                    token,
                    project_name=project.name,
                    description=description,
                    branch=str(remote.get("default_branch") or "main"),
                )
            except Exception:
                # Repository creation is still useful for recovery even when starter
                # bootstrapping needs another pass. The worker will clone and the task
                # itself can populate the repository.
                pass
            return remote, name
    return None


def _personal_fallback(project: Project):
    """Recover a managed project using the owner of an already stored credential.

    Organization-scoped creation remains the preferred path. This fallback is reached
    only after that path was exhausted. It never asks the end user for a token and it
    never uses a credential outside the current workspace.
    """
    from app.services import github_access_bridge as bridge

    if not bridge._managed_repository(project):
        return None

    with SessionLocal() as db:
        db_project = db.scalar(
            select(Project).where(
                Project.id == project.id,
                Project.workspace_id == project.workspace_id,
            )
        )
        if db_project is None:
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
        credentials.sort(key=lambda item: str(item.created_at or ""), reverse=True)

        for credential in credentials[:_MAX_CREDENTIALS]:
            try:
                token = Vault().decrypt(credential.encrypted_secret).strip()
            except (TypeError, ValueError):
                continue
            if not token:
                continue

            login = _authenticated_login(token)
            if not login:
                continue

            created = _create_personal_repository(token, login=login, project=db_project)
            if not created:
                continue
            remote, repository_name = created
            repository_url = str(remote.get("clone_url") or "").strip()
            if not repository_url or not bridge._probe(repository_url, token):
                continue

            db_project.repository_url = repository_url
            db_project.default_branch = str(remote.get("default_branch") or "main")
            try:
                config = json.loads(db_project.codex_config or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                config = {}
            if not isinstance(config, dict):
                config = {}
            config.update(
                {
                    "repository_pending": False,
                    "repository_mode": "automatic",
                    "repository_provision_state": "ready",
                    "repository_recovered_automatically": True,
                    "repository_owner_fallback": login,
                    "repository_name": repository_name,
                }
            )
            db_project.codex_config = json.dumps(config)
            db.commit()

            project.repository_url = repository_url
            project.default_branch = db_project.default_branch
            project.codex_config = db_project.codex_config

            return bridge.GitHubAccessResolution(
                True,
                bridge._git_environment(token),
                credential_id=str(credential.id),
                organization_id=str(db_project.organization_id or ""),
                message=(
                    "O DevPilot não conseguiu usar a organização configurada, então "
                    f"recriou automaticamente o repositório gerenciado na conta GitHub {login} "
                    "já cadastrada no sistema e validou o acesso."
                ),
            )
    return None


def install_managed_repository_owner_fallback() -> None:
    from app.services import github_access_bridge as bridge

    current = bridge._repair_managed_repository
    if getattr(current, "_devpilot_owner_fallback", False):
        return

    def repair_managed_repository(project: Project):
        resolved = current(project)
        if resolved is not None:
            return resolved
        return _personal_fallback(project)

    setattr(repair_managed_repository, "_devpilot_owner_fallback", True)
    bridge._repair_managed_repository = repair_managed_repository
