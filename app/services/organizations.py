from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

from app.services.policy import normalize_repository_url


SLUG_PARTS = re.compile(r"[^a-z0-9]+")
MANAGED_ORGANIZATION = "a-castilho"


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


def fetch_github_repositories(login: str, access_token: str | None = None) -> list[dict]:
    normalized_login = login.strip().lower()
    if normalized_login == MANAGED_ORGANIZATION and not access_token:
        raise RuntimeError(
            "A organização a-castilho exige um Fine-grained PAT com Resource owner = a-castilho."
        )

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot/1.0",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    repositories: list[dict] = []
    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        for page in range(1, 21):
            response = client.get(
                f"https://api.github.com/orgs/{login}/repos",
                params={"type": "all", "sort": "full_name", "per_page": 100, "page": page},
            )
            if response.status_code == 401:
                raise RuntimeError(
                    "Token GitHub inválido ou expirado. Gere um novo Fine-grained PAT para a organização."
                )
            if response.status_code == 403:
                raise RuntimeError(
                    "O token GitHub não possui acesso suficiente à organização. Para a-castilho, use "
                    "Resource owner = a-castilho e autorize os repositórios necessários; a organização "
                    "também pode exigir aprovação do token."
                )
            if response.status_code == 404:
                raise RuntimeError(
                    "Organização GitHub não encontrada ou invisível para esta credencial. Confira o login "
                    "e, para a-castilho, confirme Resource owner = a-castilho."
                )
            if response.status_code >= 400:
                raise RuntimeError(f"GitHub organization sync failed with HTTP {response.status_code}")

            items = response.json()
            if not isinstance(items, list):
                raise RuntimeError("GitHub returned an invalid repositories response")
            repositories.extend(normalize_github_repository(item) for item in items)
            if len(items) < 100:
                break
    return repositories
