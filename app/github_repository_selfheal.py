from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.db import SessionLocal
from app.github_optional_org import github_credential_candidates
from app.models import Project
from app.services.audit import record
from app.services.policy import normalize_repository_url
from app.services.vault import Vault

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 12.0


def _repository_parts(repository_url: str) -> tuple[str, str]:
    safe = normalize_repository_url(str(repository_url or ""))
    parsed = urlparse(safe)
    if str(parsed.hostname or "").lower() != "github.com":
        return "", ""
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1].removesuffix(".git")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot-GitHub-SelfHeal/2.0",
    }


def _get_json(url: str, token: str) -> tuple[int, dict]:
    try:
        response = httpx.get(url, headers=_headers(token), timeout=_TIMEOUT)
    except httpx.HTTPError:
        return 0, {}
    try:
        data = response.json() if response.content else {}
    except ValueError:
        data = {}
    return int(response.status_code), data if isinstance(data, dict) else {}


def _identity(token: str) -> str:
    status, data = _get_json(f"{_GITHUB_API}/user", token)
    return str(data.get("login") or "").strip() if status == 200 else ""


def _owner_type(token: str, owner: str) -> str:
    status, data = _get_json(f"{_GITHUB_API}/users/{owner}", token)
    if status != 200:
        return ""
    return str(data.get("type") or "").strip().lower()


def _repo_status(token: str, owner: str, name: str) -> int:
    status, _ = _get_json(f"{_GITHUB_API}/repos/{owner}/{name}", token)
    return status


def _create_repo(token: str, owner: str, owner_type: str, authenticated_login: str, name: str) -> tuple[bool, str]:
    if owner_type == "organization":
        url = f"{_GITHUB_API}/orgs/{owner}/repos"
    elif owner_type == "user" and authenticated_login.casefold() == owner.casefold():
        url = f"{_GITHUB_API}/user/repos"
    else:
        return False, "owner_not_authorized_for_creation"

    try:
        response = httpx.post(
            url,
            headers={**_headers(token), "Content-Type": "application/json"},
            json={
                "name": name,
                "private": True,
                "auto_init": True,
                "description": "Repository provisioned automatically by DevPilot.",
            },
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as error:
        return False, f"network:{type(error).__name__}"

    if response.status_code == 201:
        return True, "created"
    if response.status_code == 422 and _repo_status(token, owner, name) == 200:
        return True, "exists"
    if response.status_code in {401, 403}:
        return False, f"permission_denied:{response.status_code}"
    return False, f"http:{response.status_code}"


def repair_github_project(project: Project) -> tuple[bool, str]:
    """Make a GitHub repository usable without guessing a different owner.

    The owner stored in the project is authoritative. If the repository already
    exists and the credential can access it, execution is ready. If it is absent,
    DevPilot may create it only under that exact owner: either an organization or
    the authenticated personal account. Punctuation-based owner rewriting is not
    allowed because a user and an organization may legitimately have similar names.
    """
    owner, repo = _repository_parts(project.repository_url)
    if not owner or not repo:
        return False, "invalid_repository_url"

    with SessionLocal() as db:
        current = db.get(Project, project.id)
        if not current:
            return False, "project_not_found"

        diagnostics: list[str] = []
        for credential in github_credential_candidates(db, current)[:8]:
            try:
                token = Vault().decrypt(credential.encrypted_secret)
            except ValueError:
                diagnostics.append("credential_decrypt_failed")
                continue

            login = _identity(token)
            if not login:
                diagnostics.append("credential_identity_failed")
                continue

            status = _repo_status(token, owner, repo)
            if status == 200:
                canonical_url = f"https://github.com/{owner}/{repo}.git"
                if str(current.repository_url or "") != canonical_url:
                    current.repository_url = canonical_url
                    db.commit()
                    project.repository_url = canonical_url
                return True, f"github repository access confirmed for {owner}/{repo}"

            if status != 404:
                diagnostics.append(f"repo_http_{status}")
                continue

            owner_type = _owner_type(token, owner)
            if not owner_type:
                diagnostics.append("owner_not_found_or_not_visible")
                continue

            created, result = _create_repo(token, owner, owner_type, login, repo)
            if not created:
                diagnostics.append(result)
                continue

            canonical_url = f"https://github.com/{owner}/{repo}.git"
            current.repository_url = canonical_url
            record(
                db,
                workspace_id=current.workspace_id,
                project_id=current.id,
                actor="github-repository-selfheal",
                action="github.repository_provisioned",
                outcome="created" if result == "created" else "ready",
                details={
                    "repository": f"{owner}/{repo}",
                    "owner_type": owner_type,
                    "visibility": "private",
                    "organization_required": owner_type == "organization",
                },
            )
            db.commit()
            project.repository_url = canonical_url
            return True, f"repository {owner}/{repo} is ready ({result})"

    proof = ",".join(dict.fromkeys(diagnostics)) or "no_usable_github_credential"
    return False, proof
