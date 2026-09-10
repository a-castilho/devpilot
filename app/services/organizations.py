from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from app.services.policy import normalize_repository_url


SLUG_PARTS = re.compile(r"[^a-z0-9]+")


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


def _github_repo_endpoint(client: httpx.Client, login: str) -> tuple[str, str]:
    organization = client.get(f"https://api.github.com/orgs/{login}")
    if organization.status_code == 200:
        return f"https://api.github.com/orgs/{login}/repos", "organization"
    if organization.status_code not in {401, 403, 404}:
        raise RuntimeError(f"GitHub account lookup failed with HTTP {organization.status_code}")

    user = client.get(f"https://api.github.com/users/{login}")
    if user.status_code == 200:
        return f"https://api.github.com/users/{login}/repos", "user"
    if user.status_code == 401:
        raise RuntimeError("Token GitHub inválido ou expirado.")
    if user.status_code == 403:
        raise RuntimeError("O GitHub recusou a consulta desta conta com a credencial atual.")
    if user.status_code == 404:
        raise RuntimeError("Conta GitHub não encontrada. Confira o login informado.")
    raise RuntimeError(f"GitHub account lookup failed with HTTP {user.status_code}")


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
        endpoint, account_type = _github_repo_endpoint(client, login)
        for page in range(1, 21):
            params = {"sort": "full_name", "per_page": 100, "page": page}
            if account_type == "organization":
                params["type"] = "all"
            response = client.get(endpoint, params=params)
            if response.status_code == 401:
                raise RuntimeError("Token GitHub inválido ou expirado.")
            if response.status_code == 403:
                raise RuntimeError(
                    "O GitHub recusou a sincronização. Sem credencial, somente repositórios públicos podem ser lidos; "
                    "para privados, configure acesso GitHub autenticado no DevPilot."
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
