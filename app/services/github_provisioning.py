from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.services.organizations import normalize_github_repository


@dataclass(frozen=True)
class GitHubProvisioningError(RuntimeError):
    message: str
    status_code: int = 502

    def __str__(self) -> str:
        return self.message


def create_github_repository(
    organization_login: str,
    repository_name: str,
    description: str,
    access_token: str,
) -> dict:
    """Create a private initialized repository inside an authorized GitHub organization."""
    if not access_token.strip():
        raise GitHubProvisioningError(
            "A organização A Castilho não possui credencial GitHub autorizada para criar repositórios.",
            409,
        )

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "DevPilot/1.0",
    }
    payload = {
        "name": repository_name,
        "description": description,
        "private": True,
        "auto_init": True,
    }

    with httpx.Client(timeout=30.0, follow_redirects=True, headers=headers) as client:
        response = client.post(
            f"https://api.github.com/orgs/{organization_login}/repos",
            json=payload,
        )

    if response.status_code in {401, 403}:
        raise GitHubProvisioningError(
            "A credencial GitHub da organização não autoriza a criação de repositórios. "
            "Atualize a credencial com permissão de administração de repositórios.",
            403,
        )
    if response.status_code == 404:
        raise GitHubProvisioningError(
            "A organização A Castilho não foi encontrada ou não está acessível pela credencial configurada.",
            404,
        )
    if response.status_code == 422:
        detail = ""
        try:
            data = response.json()
            detail = str(data.get("message") or "").strip()
        except (TypeError, ValueError):
            pass
        message = "Não foi possível criar o repositório no GitHub. O nome pode já estar em uso."
        if detail:
            message = f"{message} GitHub: {detail}"
        raise GitHubProvisioningError(message, 409)
    if response.status_code >= 400:
        raise GitHubProvisioningError(
            f"Falha ao criar repositório no GitHub (HTTP {response.status_code}).",
            502,
        )

    try:
        data = response.json()
        return normalize_github_repository(data)
    except (KeyError, TypeError, ValueError) as error:
        raise GitHubProvisioningError("GitHub retornou uma resposta inválida ao criar o repositório.") from error
