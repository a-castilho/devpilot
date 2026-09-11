from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.github_optional_org import github_credential_candidates
from app.models import Organization, Project
from app.services.audit import record
from app.services.policy import normalize_repository_url
from app.services.vault import Vault

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 12.0


def _compact_login(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


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
        "User-Agent": "DevPilot-GitHub-SelfHeal/1.0",
    }


def _identity(token: str) -> str:
    try:
        response = httpx.get(f"{_GITHUB_API}/user", headers=_headers(token), timeout=_TIMEOUT)
    except httpx.HTTPError:
        return ""
    if response.status_code != 200:
        return ""
    try:
        data = response.json()
    except ValueError:
        return ""
    return str(data.get("login") or "").strip()


def _repo_status(token: str, owner: str, name: str) -> int:
    try:
        response = httpx.get(
            f"{_GITHUB_API}/repos/{owner}/{name}",
            headers=_headers(token),
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError:
        return 0
    return int(response.status_code)


def _create_personal_repo(token: str, name: str) -> tuple[bool, str, str]:
    """Create a private repository for the authenticated personal account.

    This is used only when the configured owner is a punctuation-only variant of
    the authenticated login (for example a-castilho vs acastilho) and the target
    repository is proven absent for that same account.
    """
    try:
        response = httpx.post(
            f"{_GITHUB_API}/user/repos",
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
        return False, "", f"network:{type(error).__name__}"
    if response.status_code not in {201, 422}:
        return False, "", f"http:{response.status_code}"
    try:
        data = response.json()
    except ValueError:
        data = {}
    clone_url = str(data.get("clone_url") or "").strip()
    html_url = str(data.get("html_url") or "").strip()
    return response.status_code == 201, clone_url or html_url, "created" if response.status_code == 201 else "exists"


def repair_github_project(project: Project) -> tuple[bool, str]:
    """Repair canonical GitHub owner/repository state when it is safe to do so.

    Returns (ready, proof). It never guesses across unrelated owners. Canonical
    owner repair is allowed only when owner/login differ by punctuation/case.
    """
    owner, repo = _repository_parts(project.repository_url)
    if not owner or not repo:
        return False, "invalid_repository_url"

    with SessionLocal() as db:
        current = db.get(Project, project.id)
        if not current:
            return False, "project_not_found"

        for credential in github_credential_candidates(db, current)[:8]:
            try:
                token = Vault().decrypt(credential.encrypted_secret)
            except ValueError:
                continue

            login = _identity(token)
            if not login:
                continue

            # Never redirect a project to an unrelated account. Only punctuation/
            # case variants are canonicalized automatically.
            same_account = _compact_login(owner) == _compact_login(login)
            canonical_owner = login if same_account else owner
            status = _repo_status(token, canonical_owner, repo)

            if status == 200:
                canonical_url = f"https://github.com/{canonical_owner}/{repo}.git"
                changed = str(current.repository_url or "") != canonical_url
                if changed:
                    current.repository_url = canonical_url
                    if current.organization_id:
                        organization = db.scalar(
                            select(Organization).where(
                                Organization.id == current.organization_id,
                                Organization.workspace_id == current.workspace_id,
                            )
                        )
                        if organization and _compact_login(organization.external_login) != _compact_login(canonical_owner):
                            current.organization_id = None
                    record(
                        db,
                        workspace_id=current.workspace_id,
                        project_id=current.id,
                        actor="github-repository-selfheal",
                        action="github.repository_url_canonicalized",
                        outcome="repaired",
                        details={
                            "previous_owner": owner,
                            "canonical_owner": canonical_owner,
                            "repository": repo,
                            "organization_required": False,
                        },
                    )
                    db.commit()
                    project.repository_url = canonical_url
                    project.organization_id = current.organization_id
                return True, f"github api repository access confirmed for {canonical_owner}/{repo}"

            # A repository may be provisioned automatically only for the same
            # authenticated personal account. This prevents creating repositories
            # under a different/guessed organization.
            if status == 404 and same_account:
                created, created_url, result = _create_personal_repo(token, repo)
                if created:
                    canonical_url = created_url if created_url.endswith(".git") else f"https://github.com/{login}/{repo}.git"
                    current.repository_url = canonical_url
                    if current.organization_id:
                        organization = db.scalar(
                            select(Organization).where(
                                Organization.id == current.organization_id,
                                Organization.workspace_id == current.workspace_id,
                            )
                        )
                        if organization and _compact_login(organization.external_login) != _compact_login(login):
                            current.organization_id = None
                    record(
                        db,
                        workspace_id=current.workspace_id,
                        project_id=current.id,
                        actor="github-repository-selfheal",
                        action="github.repository_provisioned",
                        outcome="created",
                        details={
                            "repository": f"{login}/{repo}",
                            "visibility": "private",
                            "organization_required": False,
                        },
                    )
                    db.commit()
                    project.repository_url = canonical_url
                    project.organization_id = current.organization_id
                    return True, f"private repository {login}/{repo} provisioned automatically"
                if result.startswith("http:403"):
                    return False, "github token authenticated but cannot create repository; repository administration permission is required"
                if result == "exists" and _repo_status(token, login, repo) == 200:
                    canonical_url = f"https://github.com/{login}/{repo}.git"
                    current.repository_url = canonical_url
                    db.commit()
                    project.repository_url = canonical_url
                    return True, f"existing repository {login}/{repo} recovered after provisioning race"

    return False, "repository unavailable to every configured GitHub credential"
