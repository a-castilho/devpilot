from __future__ import annotations

import base64
from urllib.parse import urlparse

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential
from app.services import executor
from app.services.policy import normalize_repository_url
from app.services.recovery import AutoRecoveryService, RecoveryDecision
from app.services.vault import Vault

GITHUB_HOST = "github.com"


def github_owner(repository_url: str) -> str:
    safe = normalize_repository_url(str(repository_url or ""))
    parsed = urlparse(safe)
    if str(parsed.hostname or "").lower() != GITHUB_HOST:
        return ""
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0].casefold() if len(parts) >= 2 else ""


def _metadata_scope(item: ProviderCredential) -> str:
    try:
        import json
        raw = json.loads(item.models or "{}")
    except (TypeError, ValueError):
        return ""
    if not isinstance(raw, dict):
        return ""
    return str(
        raw.get("scope")
        or raw.get("owner")
        or raw.get("organization")
        or raw.get("external_login")
        or ""
    ).strip().casefold()


def github_credential_candidates(db, project: Project) -> list[ProviderCredential]:
    """Return GitHub credentials in deterministic priority order.

    Organization is optional. A linked organization only influences priority; it is
    never required for a project to use a valid workspace credential.
    """
    owner = github_owner(project.repository_url)
    credentials = list(
        db.scalars(
            select(ProviderCredential).where(
                ProviderCredential.workspace_id == project.workspace_id,
                ProviderCredential.provider.in_(("github", "cloud:github")),
                ProviderCredential.enabled.is_(True),
            )
        ).all()
    )
    organizations = list(
        db.scalars(
            select(Organization).where(
                Organization.workspace_id == project.workspace_id,
                Organization.provider == "github",
            )
        ).all()
    )

    preferred_ids: list[str] = []
    if project.organization_id:
        linked = next((item for item in organizations if item.id == project.organization_id), None)
        if linked and str(linked.external_login or "").casefold() == owner and linked.credential_id:
            preferred_ids.append(linked.credential_id)
    for organization in organizations:
        if str(organization.external_login or "").casefold() == owner and organization.credential_id:
            if organization.credential_id not in preferred_ids:
                preferred_ids.append(organization.credential_id)

    def priority(item: ProviderCredential) -> tuple[int, int, str]:
        if item.id in preferred_ids:
            return (0, preferred_ids.index(item.id), item.id)
        scope = _metadata_scope(item)
        if scope and scope == owner:
            return (1, 0 if item.provider == "github" else 1, item.id)
        if item.provider == "github":
            return (2, 0, item.id)
        return (3, 0, item.id)

    credentials.sort(key=priority)
    return credentials


def _auth_environment(token: str) -> dict[str, str]:
    encoded = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraHeader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {encoded}",
    }


def _probe(repository_url: str, token: str | None = None):
    return executor.run(
        ["git", "ls-remote", repository_url, "HEAD"],
        timeout=30,
        env_overrides={"GIT_TERMINAL_PROMPT": "0"} if token is None else _auth_environment(token),
    )


def git_environment_without_required_organization(
    project: Project, repository_url: str | None = None
) -> dict[str, str]:
    environment = {"GIT_TERMINAL_PROMPT": "0"}
    safe_repository_url = repository_url or executor.validated_repository_url(project)
    if str(urlparse(safe_repository_url).hostname or "").lower() != GITHUB_HOST:
        return environment

    # Public repositories never need a PAT, regardless of organization state.
    try:
        if _probe(safe_repository_url).returncode == 0:
            return environment
    except Exception:
        pass

    with SessionLocal() as db:
        for credential in github_credential_candidates(db, project):
            try:
                token = Vault().decrypt(credential.encrypted_secret)
            except ValueError:
                continue
            try:
                if _probe(safe_repository_url, token).returncode == 0:
                    return _auth_environment(token)
            except Exception:
                continue
    return environment


def _recover_github_access_without_required_organization(
    self: AutoRecoveryService,
    project: Project,
    execution_attempt: int,
) -> RecoveryDecision:
    steps: list[dict] = []
    try:
        repository_url = normalize_repository_url(str(project.repository_url or ""))
    except ValueError:
        return RecoveryDecision(
            "github_auth", "needs_attention",
            "A URL persistida do repositório está fora da política Git permitida. Nenhuma credencial foi enviada.",
            False, False, "repository_url_safety_stop", steps,
        )
    owner = github_owner(repository_url)
    if not owner:
        return RecoveryDecision(
            "github_auth", "needs_attention",
            "A URL do repositório GitHub não contém owner e repositório válidos.",
            False, False, "repository_url_safety_stop", steps,
        )

    # First prove whether credentials are needed at all.
    try:
        if _probe(repository_url).returncode == 0:
            return RecoveryDecision(
                "github_auth", "resolved",
                "O repositório está acessível sem credencial; a execução será retomada.",
                execution_attempt < self.MAX_ATTEMPTS, False, "github_public_access", steps,
            )
    except Exception:
        pass

    with SessionLocal() as db:
        credentials = github_credential_candidates(db, project)
        if not credentials:
            return RecoveryDecision(
                "github_auth", "needs_authorization",
                "Nenhuma credencial GitHub ativa está disponível neste workspace para testar o acesso ao repositório.",
                False, True, "request_github_authorization", steps,
            )

        for index, credential in enumerate(credentials[:8], start=1):
            try:
                token = Vault().decrypt(credential.encrypted_secret)
            except ValueError:
                continue
            result = self._git_ls_remote(repository_url, token)
            if result.returncode == 0:
                steps.append({
                    "state": "credential_validated",
                    "attempt": execution_attempt,
                    "candidate": index,
                    "repository_owner": owner,
                    "organization_required": False,
                    "message": "Acesso ao repositório validado. Organização é contexto opcional e não bloqueia a execução.",
                })
                return RecoveryDecision(
                    "github_auth", "resolved",
                    "A credencial GitHub cadastrada foi validada para o repositório e a execução será retomada.",
                    execution_attempt < self.MAX_ATTEMPTS,
                    False,
                    "github_workspace_credential_recheck",
                    steps,
                )
            steps.append({
                "state": "credential_rejected",
                "attempt": execution_attempt,
                "candidate": index,
                "message": "A credencial testada não possui acesso suficiente ao repositório.",
            })

    return RecoveryDecision(
        "github_auth", "needs_authorization",
        "As credenciais GitHub disponíveis neste workspace foram testadas e nenhuma possui acesso ao repositório.",
        False, True, "request_github_authorization", steps,
    )


def install() -> None:
    # Replace both the normal executor path and recovery path. Organization remains
    # useful metadata, but it is no longer an authorization prerequisite.
    executor.git_environment = git_environment_without_required_organization
    AutoRecoveryService._recover_github_access = _recover_github_access_without_required_organization


install()
