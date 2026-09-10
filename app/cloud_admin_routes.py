from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential
from app.security import Principal, Role, require_roles
from app.services.audit import record
from app.services.vault import Vault


router = APIRouter(prefix="/api/admin/clouds", tags=["admin-clouds"])
manage_clouds = require_roles(Role.SUPER_ADMIN)

_CREDENTIAL_LABEL = "cloud-admin"
_PROVIDER_PREFIX = "cloud:"
_LEGACY_CREDENTIAL_LABEL = "Principal"
_LEGACY_PROVIDER_PREFIX = "cloud-"
_REQUEST_TIMEOUT = 10.0

CLOUD_PROVIDERS: dict[str, dict[str, str]] = {
    "vercel": {
        "name": "Vercel",
        "dashboard_url": "https://vercel.com/dashboard",
        "scope_label": "Team ID ou slug",
    },
    "render": {
        "name": "Render",
        "dashboard_url": "https://dashboard.render.com",
        "scope_label": "Workspace / Owner ID",
    },
    "neon": {
        "name": "Neon",
        "dashboard_url": "https://console.neon.tech",
        "scope_label": "Organization ID (opcional)",
    },
    "github": {
        "name": "GitHub",
        "dashboard_url": "https://github.com",
        "scope_label": "Organização (opcional)",
    },
}


class CloudCredentialUpdate(BaseModel):
    secret: str | None = Field(default=None, min_length=8, max_length=10_000)
    enabled: bool = True
    scope: str = Field(default="", max_length=200)


class CloudProviderError(RuntimeError):
    pass


def _provider(provider: str) -> tuple[str, dict[str, str]]:
    key = provider.strip().lower()
    config = CLOUD_PROVIDERS.get(key)
    if not config:
        raise HTTPException(status_code=404, detail="Cloud não suportado")
    return key, config


def _provider_storage_key(provider: str) -> str:
    return f"{_PROVIDER_PREFIX}{provider}"


def _credential(
    db: Session,
    principal: Principal,
    provider: str,
) -> ProviderCredential | None:
    canonical = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == principal.workspace_id,
            ProviderCredential.provider == _provider_storage_key(provider),
            ProviderCredential.label == _CREDENTIAL_LABEL,
        )
    )
    if canonical:
        return canonical

    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == principal.workspace_id,
            ProviderCredential.provider == f"{_LEGACY_PROVIDER_PREFIX}{provider}",
            ProviderCredential.label == _LEGACY_CREDENTIAL_LABEL,
        )
    )


def _legacy_payload(item: ProviderCredential) -> dict[str, Any]:
    try:
        value = json.loads(Vault().decrypt(item.encrypted_secret))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _metadata(item: ProviderCredential | None) -> dict[str, Any]:
    if not item:
        return {}
    try:
        value = json.loads(item.models or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        value = {}
    metadata = value if isinstance(value, dict) else {}
    if metadata.get("scope"):
        return metadata

    legacy = _legacy_payload(item)
    if legacy.get("account_id"):
        metadata = dict(metadata)
        metadata["scope"] = str(legacy.get("account_id") or "")
    return metadata


def _summary(provider: str, item: ProviderCredential | None) -> dict[str, Any]:
    config = CLOUD_PROVIDERS[provider]
    metadata = _metadata(item)
    return {
        "provider": provider,
        "name": config["name"],
        "configured": item is not None,
        "enabled": bool(item.enabled) if item else False,
        "scope": str(metadata.get("scope") or ""),
        "dashboard_url": config["dashboard_url"],
        "scope_label": config["scope_label"],
        "created_at": item.created_at if item else None,
    }


def _decrypt(item: ProviderCredential) -> str:
    try:
        secret = Vault().decrypt(item.encrypted_secret)
    except ValueError as error:
        raise CloudProviderError("A credencial salva não pôde ser descriptografada.") from error

    try:
        payload = json.loads(secret)
    except (TypeError, ValueError, json.JSONDecodeError):
        return secret
    if isinstance(payload, dict) and str(payload.get("token") or "").strip():
        return str(payload["token"]).strip()
    return secret


def _headers(provider: str, secret: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {secret}",
        "Accept": "application/json",
        "User-Agent": "DevPilot-Cloud-Admin/1.0",
    }
    if provider == "github":
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers


def _vercel_scope_params(scope: str) -> dict[str, str]:
    if not scope:
        return {}
    if scope.startswith("team_"):
        return {"teamId": scope}
    return {"slug": scope}


def _provider_request(
    provider: str,
    secret: str,
    scope: str,
    *,
    resources: bool,
) -> Any:
    if provider == "vercel":
        if resources or scope:
            url = "https://api.vercel.com/v9/projects"
            params: dict[str, Any] = {"limit": 50 if resources else 1}
            params.update(_vercel_scope_params(scope))
        else:
            url = "https://api.vercel.com/v2/user"
            params = None
    elif provider == "render":
        url = "https://api.render.com/v1/services"
        params = {"ownerId": scope, "limit": 50} if scope else {"limit": 50}
    elif provider == "neon":
        url = "https://console.neon.tech/api/v2/projects"
        params = {"limit": 50}
        if scope:
            params["org_id"] = scope
    elif provider == "github":
        encoded_scope = quote(scope, safe="")
        if resources and scope:
            url = f"https://api.github.com/orgs/{encoded_scope}/repos"
            params = {"per_page": 50, "sort": "updated"}
        elif resources:
            url = "https://api.github.com/user/repos"
            params = {
                "per_page": 50,
                "sort": "updated",
                "affiliation": "owner,collaborator,organization_member",
            }
        elif scope:
            url = f"https://api.github.com/user/memberships/orgs/{encoded_scope}"
            params = None
        else:
            url = "https://api.github.com/user"
            params = None
    else:
        raise CloudProviderError("Cloud não suportado")

    try:
        response = httpx.get(
            url,
            headers=_headers(provider, secret),
            params=params,
            timeout=_REQUEST_TIMEOUT,
            follow_redirects=True,
        )
    except httpx.HTTPError as error:
        raise CloudProviderError("Não foi possível conectar ao cloud agora.") from error

    if response.status_code >= 400:
        raise CloudProviderError(
            f"{CLOUD_PROVIDERS[provider]['name']} respondeu HTTP {response.status_code}."
        )
    try:
        return response.json()
    except ValueError as error:
        raise CloudProviderError("O cloud respondeu com um formato inesperado.") from error


def _test_payload(provider: str, data: Any) -> dict[str, Any]:
    identity = ""
    resource_count: int | None = None

    if provider == "vercel" and isinstance(data, dict):
        projects = data.get("projects")
        if isinstance(projects, list):
            resource_count = len(projects)
        else:
            user = data.get("user") if isinstance(data.get("user"), dict) else data
            identity = str(user.get("username") or user.get("email") or user.get("name") or "")
    elif provider == "github" and isinstance(data, dict):
        organization = data.get("organization") if isinstance(data.get("organization"), dict) else {}
        identity = str(
            data.get("login")
            or data.get("name")
            or organization.get("login")
            or organization.get("name")
            or ""
        )
    elif provider == "neon" and isinstance(data, dict):
        projects = data.get("projects")
        resource_count = len(projects) if isinstance(projects, list) else 0
    elif provider == "render" and isinstance(data, list):
        resource_count = len(data)

    return {
        "ok": True,
        "provider": provider,
        "identity": identity,
        "resource_count": resource_count,
    }


def _resource_payload(provider: str, data: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    if provider == "vercel" and isinstance(data, dict):
        source = data.get("projects") if isinstance(data.get("projects"), list) else []
        for project in source[:50]:
            if not isinstance(project, dict):
                continue
            items.append(
                {
                    "id": str(project.get("id") or ""),
                    "name": str(project.get("name") or "Projeto"),
                    "kind": str(project.get("framework") or "project"),
                    "status": "active",
                    "url": "",
                }
            )
    elif provider == "render" and isinstance(data, list):
        for wrapper in data[:50]:
            raw = wrapper.get("service") if isinstance(wrapper, dict) else None
            service = raw if isinstance(raw, dict) else (wrapper if isinstance(wrapper, dict) else {})
            details = service.get("serviceDetails")
            details = details if isinstance(details, dict) else {}
            suspended = str(service.get("suspended") or "").lower()
            status = "suspended" if suspended in {"true", "suspended"} else "active"
            items.append(
                {
                    "id": str(service.get("id") or ""),
                    "name": str(service.get("name") or "Serviço"),
                    "kind": str(service.get("type") or details.get("runtime") or "service"),
                    "status": status,
                    "url": str(details.get("url") or ""),
                }
            )
    elif provider == "neon" and isinstance(data, dict):
        source = data.get("projects") if isinstance(data.get("projects"), list) else []
        for project in source[:50]:
            if not isinstance(project, dict):
                continue
            items.append(
                {
                    "id": str(project.get("id") or ""),
                    "name": str(project.get("name") or "Projeto"),
                    "kind": "postgres",
                    "status": "active",
                    "url": "",
                }
            )
    elif provider == "github" and isinstance(data, list):
        for repo in data[:50]:
            if not isinstance(repo, dict):
                continue
            items.append(
                {
                    "id": str(repo.get("id") or ""),
                    "name": str(repo.get("full_name") or repo.get("name") or "Repositório"),
                    "kind": str(repo.get("visibility") or "repository"),
                    "status": "archived" if repo.get("archived") else "active",
                    "url": str(repo.get("html_url") or ""),
                }
            )
    return items


def _require_item(
    db: Session,
    principal: Principal,
    provider: str,
) -> ProviderCredential:
    item = _credential(db, principal, provider)
    if not item:
        raise HTTPException(status_code=404, detail="Credencial do cloud não configurada")
    return item


@router.get("")
def list_clouds(
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_clouds),
):
    return [_summary(provider, _credential(db, principal, provider)) for provider in CLOUD_PROVIDERS]


@router.put("/{provider}")
def save_cloud(
    provider: str,
    payload: CloudCredentialUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_clouds),
):
    provider, _ = _provider(provider)
    item = _credential(db, principal, provider)
    secret = payload.secret.strip() if payload.secret else ""

    if not item and not secret:
        raise HTTPException(status_code=422, detail="Informe o token para configurar este cloud")

    if not item:
        item = ProviderCredential(
            workspace_id=principal.workspace_id,
            provider=_provider_storage_key(provider),
            label=_CREDENTIAL_LABEL,
            encrypted_secret=Vault().encrypt(secret),
            models="{}",
            enabled=payload.enabled,
        )
        db.add(item)
    else:
        is_legacy = (
            item.provider == f"{_LEGACY_PROVIDER_PREFIX}{provider}"
            and item.label == _LEGACY_CREDENTIAL_LABEL
        )
        if is_legacy:
            legacy_payload = _legacy_payload(item)
            current_token = str(legacy_payload.get("token") or "").strip()
            next_token = secret or current_token
            if next_token:
                item.encrypted_secret = Vault().encrypt(
                    json.dumps(
                        {"token": next_token, "account_id": payload.scope.strip()},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
        elif secret:
            item.encrypted_secret = Vault().encrypt(secret)

    item.enabled = payload.enabled
    item.models = json.dumps(
        {"scope": payload.scope.strip()},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    db.flush()
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="cloud.credential_saved",
        details={
            "provider": provider,
            "enabled": item.enabled,
            "scope_configured": bool(payload.scope.strip()),
            "secret_rotated": bool(secret),
        },
    )
    db.commit()
    return _summary(provider, item)


@router.delete("/{provider}", status_code=204)
def delete_cloud(
    provider: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_clouds),
):
    provider, _ = _provider(provider)
    item = _require_item(db, principal, provider)
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="cloud.credential_deleted",
        details={"provider": provider},
    )
    db.delete(item)
    db.commit()
    return None


@router.post("/{provider}/test")
def test_cloud(
    provider: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_clouds),
):
    provider, _ = _provider(provider)
    item = _require_item(db, principal, provider)
    scope = str(_metadata(item).get("scope") or "")
    try:
        result = _test_payload(
            provider,
            _provider_request(provider, _decrypt(item), scope, resources=False),
        )
    except CloudProviderError as error:
        record(
            db,
            workspace_id=principal.workspace_id,
            actor=principal.actor,
            action="cloud.connection_test",
            outcome="failed",
            details={"provider": provider},
        )
        db.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error

    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="cloud.connection_test",
        details={"provider": provider},
    )
    db.commit()
    return result


@router.get("/{provider}/resources")
def list_cloud_resources(
    provider: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(manage_clouds),
):
    provider, _ = _provider(provider)
    item = _require_item(db, principal, provider)
    if not item.enabled:
        raise HTTPException(status_code=409, detail="Cloud está desativado")
    scope = str(_metadata(item).get("scope") or "")
    try:
        resources = _resource_payload(
            provider,
            _provider_request(provider, _decrypt(item), scope, resources=True),
        )
    except CloudProviderError as error:
        record(
            db,
            workspace_id=principal.workspace_id,
            actor=principal.actor,
            action="cloud.resources_listed",
            outcome="failed",
            details={"provider": provider},
        )
        db.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error

    record(
        db,
        workspace_id=principal.workspace_id,
        actor=principal.actor,
        action="cloud.resources_listed",
        details={"provider": provider, "resource_count": len(resources)},
    )
    db.commit()
    return {"provider": provider, "resources": resources}
