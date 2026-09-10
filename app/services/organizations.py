from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape

import httpx

from app.services.policy import normalize_repository_url


SLUG_PARTS = re.compile(r"[^a-z0-9]+")
REPO_HREF_RE = re.compile(r'href="/([^/\"?#]+)/([^/\"?#]+)"')


def now() -> datetime:
    return datetime.now(timezone.utc)


def project_slug(name: str) -> str:
    value = SLUG_PARTS.sub("-", name.lower()).strip("-")[:100]
    if not value:
        value = "repo"
    if len(value) == 1:
        value = f"{value}-repo"
    return value


def normalize_github_repository(payload: dict) -> dict:
    clone_url = normalize_repository_url(str(payload.get("clone_url") or ""))
    return {
        "external_id": str(payload["id"]),
        "name": str(payload["name"]),
        "full_name": str(payload["full_name"]),
        "description": str(payload.get("description") or ""),
        "clone_url": clone_url,
        "default_branch": str(payload.get("default_branch") or "main"),
        "visibility": str(
            payload.get("visibility") or ("private" if payload.get("private") else "public")
        ),
        "archived": bool(payload.get("archived", False)),
    }


def _public_repositories_from_html(client: httpx.Client, login: str) -> list[dict]:
    login_cf = login.casefold()
    urls = [
        f"https://github.com/orgs/{login}/repositories?type=all",
        f"https://github.com/{login}?tab=repositories",
    ]
    names: set[str] = set()
    for url in urls:
        response = client.get(url, headers={"Accept": "text/html"})
        if response.status_code >= 400:
            continue
        body = unescape(response.text)
        for owner, name in REPO_HREF_RE.findall(body):
            if owner.casefold() != login_cf:
                continue
            if name in {"followers", "following", "packages", "people", "projects", "repositories"}:
                continue
            if name.startswith("?"):
                continue
            names.add(name)
        if names:
            break

    return [
        {
            "external_id": f"public:{login}/{name}",
            "name": name,
            "full_name": f"{login}/{name}",
            "description": "",
            "clone_url": normalize_repository_url(f"https://github.com/{login}/{name}.git"),
            "default_branch": "main",
            "visibility": "public",
            "archived": False,
        }
        for name in sorted(names, key=str.casefold)
    ]


def _github_repo_endpoint(client: httpx.Client, login: str) -> tuple[str, str]:
    organization = client.get(f"https://api.github.com/orgs/{login}")
    if organization.status_code == 200:
        return f"https://api.github.com/orgs/{login}/repos", "organization"
    if organization.status_code == 404:
        user = client.get(f"https://api.github.com/users/{login}")
        if user.status_code == 200:
            return f"https://api.github.com/users/{login}/repos", "user"
        if user.status_code == 404:
            raise RuntimeError("Conta GitHub não encontrada. Confira o login informado.")
        if user.status_code == 401:
            raise RuntimeError("Token GitHub inválido ou expirado.")
        if user.status_code >= 400:
            raise RuntimeError(f"GitHub account lookup failed with HTTP {user.status_code}")
    if organization.status_code == 401:
        raise RuntimeError("Token GitHub inválido ou expirado.")
    if organization.status_code >= 400:
        raise RuntimeError(f"GitHub account lookup failed with HTTP {organization.status_code}")
    raise RuntimeError("Conta GitHub não encontrada.")


def fetch_github_repositories(login: str, access_token: str | None = None) -> list[dict]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot/1.0",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    repositories: list[dict] = []
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        try:
            endpoint, account_type = _github_repo_endpoint(client, login)
        except RuntimeError as error:
            if not access_token and "HTTP 403" in str(error):
                public_items = _public_repositories_from_html(client, login)
                if public_items:
                    return public_items
            raise

        for page in range(1, 21):
            params = {"sort": "full_name", "per_page": 100, "page": page}
            if account_type == "organization":
                params["type"] = "all" if access_token else "public"
            response = client.get(endpoint, params=params)
            if response.status_code == 401:
                raise RuntimeError("Token GitHub inválido ou expirado.")
            if response.status_code == 403:
                if not access_token:
                    public_items = _public_repositories_from_html(client, login)
                    if public_items:
                        return public_items
                raise RuntimeError(
                    "O GitHub recusou a sincronização pela API. Sem credencial, o DevPilot tentou o fallback público, "
                    "mas não conseguiu obter repositórios; para privados, configure acesso GitHub autenticado."
                )
            if response.status_code == 404:
                raise RuntimeError("Conta GitHub não encontrada ou invisível para a credencial atual.")
            if response.status_code >= 400:
                raise RuntimeError(f"GitHub repository sync failed with HTTP {response.status_code}")

            items = response.json()
            if not isinstance(items, list):
                raise RuntimeError("GitHub returned an invalid repositories response")
            repositories.extend(normalize_github_repository(item) for item in items)
            if len(items) < 100:
                break
    return repositories
