from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
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
_REQUEST_TIMEOUT = 10.0
_RENDER_SERVICE_NAME = "devpilot-homolog-docker"
_RENDER_REPOSITORY = "https://github.com/a-castilho/devpilot"
_RENDER_BRANCH = "fix/mobile-standard-top-back"
_RENDER_DEPLOY_MAX_WAIT_SECONDS = 20 * 60
_RENDER_TERMINAL_FAILURES = {"build_failed", "update_failed", "canceled", "pre_deploy_failed"}

CLOUD_PROVIDERS: dict[str, dict[str, str]] = {
    "vercel": {"name": "Vercel", "dashboard_url": "https://vercel.com/dashboard", "scope_label": "Team ID ou slug"},
    "render": {"name": "Render", "dashboard_url": "https://dashboard.render.com", "scope_label": "Workspace / Owner ID"},
    "neon": {"name": "Neon", "dashboard_url": "https://console.neon.tech", "scope_label": "Organization ID (opcional)"},
    "github": {"name": "GitHub", "dashboard_url": "https://github.com", "scope_label": "Organização (opcional)"},
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


def _credential(db: Session, principal: Principal, provider: str) -> ProviderCredential | None:
    return db.scalar(select(ProviderCredential).where(
        ProviderCredential.workspace_id == principal.workspace_id,
        ProviderCredential.provider == _provider_storage_key(provider),
        ProviderCredential.label == _CREDENTIAL_LABEL,
    ))


def _metadata(item: ProviderCredential | None) -> dict[str, Any]:
    if not item:
        return {}
    try:
        value = json.loads(item.models or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


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
        return Vault().decrypt(item.encrypted_secret)
    except ValueError as error:
        raise CloudProviderError("A credencial salva não pôde ser descriptografada.") from error


def _headers(provider: str, secret: str) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {secret}", "Accept": "application/json", "User-Agent": "DevPilot-Cloud-Admin/1.0"}
    if provider == "github":
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers


def _retry_request(method: str, url: str, *, headers: dict[str, str], params: dict[str, Any] | None = None, json_body: Any = None, timeout: float = _REQUEST_TIMEOUT) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = httpx.request(method, url, headers=headers, params=params, json=json_body, timeout=timeout, follow_redirects=True)
            if response.status_code < 500 or attempt == 2:
                return response
        except httpx.HTTPError as error:
            last_error = error
            if attempt == 2:
                break
        time.sleep(0.35 * (2 ** attempt))
    raise CloudProviderError("Não foi possível conectar ao cloud agora.") from last_error


def _vercel_scope_params(scope: str) -> dict[str, str]:
    if not scope:
        return {}
    return {"teamId": scope} if scope.startswith("team_") else {"slug": scope}


def _provider_request(provider: str, secret: str, scope: str, *, resources: bool) -> Any:
    if provider == "vercel":
        if resources or scope:
            url = "https://api.vercel.com/v9/projects"
            params: dict[str, Any] | None = {"limit": 50 if resources else 1}
            params.update(_vercel_scope_params(scope))
        else:
            url, params = "https://api.vercel.com/v2/user", None
    elif provider == "render":
        url = "https://api.render.com/v1/services"
        params = {"limit": 50, **({"ownerId": scope} if scope else {})}
    elif provider == "neon":
        url = "https://console.neon.tech/api/v2/projects"
        params = {"limit": 50, **({"org_id": scope} if scope else {})}
    elif provider == "github":
        encoded_scope = quote(scope, safe="")
        if resources and scope:
            url, params = f"https://api.github.com/orgs/{encoded_scope}/repos", {"per_page": 50, "sort": "updated"}
        elif resources:
            url, params = "https://api.github.com/user/repos", {"per_page": 50, "sort": "updated", "affiliation": "owner,collaborator,organization_member"}
        elif scope:
            url, params = f"https://api.github.com/user/memberships/orgs/{encoded_scope}", None
        else:
            url, params = "https://api.github.com/user", None
    else:
        raise CloudProviderError("Cloud não suportado")

    response = _retry_request("GET", url, headers=_headers(provider, secret), params=params)
    if response.status_code >= 400:
        raise CloudProviderError(f"{CLOUD_PROVIDERS[provider]['name']} respondeu HTTP {response.status_code}.")
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
        identity = str(data.get("login") or data.get("name") or organization.get("login") or organization.get("name") or "")
    elif provider == "neon" and isinstance(data, dict):
        projects = data.get("projects")
        resource_count = len(projects) if isinstance(projects, list) else 0
    elif provider == "render" and isinstance(data, list):
        resource_count = len(data)
    return {"ok": True, "provider": provider, "identity": identity, "resource_count": resource_count}


def _resource_payload(provider: str, data: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if provider == "vercel" and isinstance(data, dict):
        source = data.get("projects") if isinstance(data.get("projects"), list) else []
        for project in source[:50]:
            if isinstance(project, dict):
                items.append({"id": str(project.get("id") or ""), "name": str(project.get("name") or "Projeto"), "kind": str(project.get("framework") or "project"), "status": "active", "url": ""})
    elif provider == "render" and isinstance(data, list):
        for wrapper in data[:50]:
            raw = wrapper.get("service") if isinstance(wrapper, dict) else None
            service = raw if isinstance(raw, dict) else (wrapper if isinstance(wrapper, dict) else {})
            details = service.get("serviceDetails") if isinstance(service.get("serviceDetails"), dict) else {}
            suspended = str(service.get("suspended") or "").lower()
            items.append({"id": str(service.get("id") or ""), "name": str(service.get("name") or "Serviço"), "kind": str(service.get("type") or details.get("runtime") or "service"), "status": "suspended" if suspended in {"true", "suspended"} else "active", "url": str(details.get("url") or "")})
    elif provider == "neon" and isinstance(data, dict):
        source = data.get("projects") if isinstance(data.get("projects"), list) else []
        for project in source[:50]:
            if isinstance(project, dict):
                items.append({"id": str(project.get("id") or ""), "name": str(project.get("name") or "Projeto"), "kind": "postgres", "status": "active", "url": ""})
    elif provider == "github" and isinstance(data, list):
        for repo in data[:50]:
            if isinstance(repo, dict):
                items.append({"id": str(repo.get("id") or ""), "name": str(repo.get("full_name") or repo.get("name") or "Repositório"), "kind": str(repo.get("visibility") or "repository"), "status": "archived" if repo.get("archived") else "active", "url": str(repo.get("html_url") or "")})
    return items


def _require_item(db: Session, principal: Principal, provider: str) -> ProviderCredential:
    item = _credential(db, principal, provider)
    if not item:
        raise HTTPException(status_code=404, detail="Credencial do cloud não configurada")
    return item


def _runtime_env_vars() -> list[dict[str, str]]:
    required = ("DEVPILOT_DATABASE_URL", "DEVPILOT_AUTH_SECRET", "DEVPILOT_ENCRYPTION_KEY")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise CloudProviderError("Homologação atual não possui variáveis obrigatórias: " + ", ".join(missing))
    values: dict[str, str] = {
        "DEVPILOT_ENV": "homologation",
        "DEVPILOT_DATA_DIR": "/tmp/devpilot",
        "DEVPILOT_REPOSITORIES_DIR": "/tmp/devpilot/repositories",
        "DEVPILOT_HOST_ACTIONS_DIR": "/tmp/devpilot/host-actions",
        "DEVPILOT_AUTH_TOKEN_TTL_SECONDS": os.getenv("DEVPILOT_AUTH_TOKEN_TTL_SECONDS", "3600"),
        "DEVPILOT_EXECUTION_ENABLED": "true",
        "DEVPILOT_EMBEDDED_WORKER": "true",
        "DEVPILOT_ALLOWED_GIT_HOSTS": os.getenv("DEVPILOT_ALLOWED_GIT_HOSTS", "github.com"),
    }
    for name in ("DEVPILOT_DATABASE_URL", "DEVPILOT_AUTH_SECRET", "DEVPILOT_ENCRYPTION_KEY", "DEVPILOT_BOOTSTRAP_TOKEN", "OPENAI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            values[name] = value
    return [{"key": key, "value": value} for key, value in values.items()]


def _render_service_url(service: dict[str, Any]) -> str:
    details = service.get("serviceDetails") if isinstance(service.get("serviceDetails"), dict) else {}
    return str(details.get("url") or service.get("url") or "")


def _find_render_service(secret: str, owner_id: str) -> dict[str, Any] | None:
    params: dict[str, Any] = {"limit": 100, **({"ownerId": owner_id} if owner_id else {})}
    response = _retry_request("GET", "https://api.render.com/v1/services", headers=_headers("render", secret), params=params)
    if response.status_code >= 400:
        raise CloudProviderError(f"Render respondeu HTTP {response.status_code} ao listar serviços.")
    try:
        data = response.json()
    except ValueError as error:
        raise CloudProviderError("Render retornou resposta inválida ao listar serviços.") from error
    if not isinstance(data, list):
        return None
    for wrapper in data:
        if not isinstance(wrapper, dict):
            continue
        service = wrapper.get("service") if isinstance(wrapper.get("service"), dict) else wrapper
        if str(service.get("name") or "") == _RENDER_SERVICE_NAME:
            return service
    return None


def _provision_render_homologation(secret: str, owner_id: str) -> dict[str, Any]:
    if not owner_id:
        raise CloudProviderError("Informe o Workspace / Owner ID da Render antes de provisionar.")
    existing = _find_render_service(secret, owner_id)
    if existing:
        return {"ok": True, "created": False, "service_id": str(existing.get("id") or ""), "name": str(existing.get("name") or _RENDER_SERVICE_NAME), "url": _render_service_url(existing), "status": "existing", "poll_after_seconds": 5, "max_wait_seconds": _RENDER_DEPLOY_MAX_WAIT_SECONDS}

    body: dict[str, Any] = {
        "type": "web_service",
        "name": _RENDER_SERVICE_NAME,
        "ownerId": owner_id,
        "repo": _RENDER_REPOSITORY,
        "branch": _RENDER_BRANCH,
        "autoDeploy": "yes",
        "envVars": _runtime_env_vars(),
        "serviceDetails": {"runtime": "docker", "plan": "free", "healthCheckPath": "/health", "envSpecificDetails": {"dockerfilePath": "./Dockerfile", "dockerContext": "."}},
    }
    response = _retry_request("POST", "https://api.render.com/v1/services", headers={**_headers("render", secret), "Content-Type": "application/json"}, json_body=body, timeout=30.0)
    if response.status_code >= 400:
        detail = response.text[:300].strip()
        raise CloudProviderError(f"Render respondeu HTTP {response.status_code} ao criar homologação" + (f": {detail}" if detail else "."))
    try:
        data = response.json() if response.content else {}
    except ValueError as error:
        raise CloudProviderError("Render não retornou JSON válido ao criar homologação.") from error
    service = data.get("service") if isinstance(data, dict) and isinstance(data.get("service"), dict) else data
    if not isinstance(service, dict) or not service.get("id"):
        raise CloudProviderError("Render não retornou o serviço criado.")
    return {"ok": True, "created": True, "service_id": str(service.get("id") or ""), "name": str(service.get("name") or _RENDER_SERVICE_NAME), "url": _render_service_url(service), "status": "deploying", "poll_after_seconds": 5, "max_wait_seconds": _RENDER_DEPLOY_MAX_WAIT_SECONDS}


def _parse_render_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _render_deploy_status(secret: str, owner_id: str) -> dict[str, Any]:
    service = _find_render_service(secret, owner_id)
    if not service:
        return {"ok": True, "status": "not_provisioned", "ready": False, "timed_out": False, "terminal": False, "service_id": "", "url": "", "next_poll_seconds": 0, "max_wait_seconds": _RENDER_DEPLOY_MAX_WAIT_SECONDS}
    service_id = str(service.get("id") or "")
    service_url = _render_service_url(service).rstrip("/")
    response = _retry_request("GET", f"https://api.render.com/v1/services/{service_id}/deploys", headers=_headers("render", secret), params={"limit": 1})
    if response.status_code >= 400:
        raise CloudProviderError(f"Render respondeu HTTP {response.status_code} ao consultar deploy.")
    try:
        data = response.json()
    except ValueError as error:
        raise CloudProviderError("Render retornou resposta inválida ao consultar deploy.") from error
    deploy: dict[str, Any] = {}
    if isinstance(data, list) and data:
        first = data[0]
        deploy = first.get("deploy") if isinstance(first, dict) and isinstance(first.get("deploy"), dict) else (first if isinstance(first, dict) else {})
    deploy_status = str(deploy.get("status") or "pending")
    started = _parse_render_time(deploy.get("startedAt") or deploy.get("createdAt"))
    elapsed = max(0, int((datetime.now(timezone.utc) - started).total_seconds())) if started else 0
    timed_out = deploy_status not in _RENDER_TERMINAL_FAILURES | {"live"} and elapsed > _RENDER_DEPLOY_MAX_WAIT_SECONDS
    health_ok = False
    health_status = 0
    if deploy_status == "live" and service_url:
        try:
            health = httpx.get(f"{service_url}/health", timeout=6.0, follow_redirects=True)
            health_status = health.status_code
            health_ok = 200 <= health.status_code < 400
        except httpx.HTTPError:
            health_ok = False
    ready = deploy_status == "live" and health_ok
    terminal = ready or timed_out or deploy_status in _RENDER_TERMINAL_FAILURES
    if terminal:
        next_poll = 0
    elif elapsed < 60:
        next_poll = 5
    elif elapsed < 300:
        next_poll = 10
    else:
        next_poll = 20
    return {
        "ok": True,
        "status": "ready" if ready else ("timeout" if timed_out else deploy_status),
        "render_status": deploy_status,
        "ready": ready,
        "timed_out": timed_out,
        "terminal": terminal,
        "service_id": service_id,
        "url": service_url,
        "deploy_id": str(deploy.get("id") or ""),
        "elapsed_seconds": elapsed,
        "health_ok": health_ok,
        "health_status_code": health_status,
        "next_poll_seconds": next_poll,
        "max_wait_seconds": _RENDER_DEPLOY_MAX_WAIT_SECONDS,
    }


@router.get("")
def list_clouds(db: Session = Depends(get_db), principal: Principal = Depends(manage_clouds)):
    return [_summary(provider, _credential(db, principal, provider)) for provider in CLOUD_PROVIDERS]


@router.post("/render/provision-homologation")
def provision_render_homologation(db: Session = Depends(get_db), principal: Principal = Depends(manage_clouds)):
    item = _require_item(db, principal, "render")
    if not item.enabled:
        raise HTTPException(status_code=409, detail="Render está desativado")
    owner_id = str(_metadata(item).get("scope") or "").strip()
    try:
        result = _provision_render_homologation(_decrypt(item), owner_id)
    except CloudProviderError as error:
        record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="cloud.render_homologation_provisioned", outcome="failed", details={"service_name": _RENDER_SERVICE_NAME})
        db.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error
    record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="cloud.render_homologation_provisioned", details={"service_name": result["name"], "service_id": result["service_id"], "created": result["created"]})
    db.commit()
    return result


@router.get("/render/provision-homologation/status")
def render_homologation_status(db: Session = Depends(get_db), principal: Principal = Depends(manage_clouds)):
    item = _require_item(db, principal, "render")
    if not item.enabled:
        raise HTTPException(status_code=409, detail="Render está desativado")
    owner_id = str(_metadata(item).get("scope") or "").strip()
    try:
        return _render_deploy_status(_decrypt(item), owner_id)
    except CloudProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.put("/{provider}")
def save_cloud(provider: str, payload: CloudCredentialUpdate, db: Session = Depends(get_db), principal: Principal = Depends(manage_clouds)):
    provider, _ = _provider(provider)
    item = _credential(db, principal, provider)
    secret = payload.secret.strip() if payload.secret else ""
    if not item and not secret:
        raise HTTPException(status_code=422, detail="Informe o token para configurar este cloud")
    if not item:
        item = ProviderCredential(workspace_id=principal.workspace_id, provider=_provider_storage_key(provider), label=_CREDENTIAL_LABEL, encrypted_secret=Vault().encrypt(secret), models="{}", enabled=payload.enabled)
        db.add(item)
    elif secret:
        item.encrypted_secret = Vault().encrypt(secret)
    item.enabled = payload.enabled
    item.models = json.dumps({"scope": payload.scope.strip()}, ensure_ascii=False, separators=(",", ":"))
    db.flush()
    record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="cloud.credential_saved", details={"provider": provider, "enabled": item.enabled, "scope_configured": bool(payload.scope.strip()), "secret_rotated": bool(secret)})
    db.commit()
    return _summary(provider, item)


@router.delete("/{provider}", status_code=204)
def delete_cloud(provider: str, db: Session = Depends(get_db), principal: Principal = Depends(manage_clouds)):
    provider, _ = _provider(provider)
    item = _require_item(db, principal, provider)
    record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="cloud.credential_deleted", details={"provider": provider})
    db.delete(item)
    db.commit()
    return None


@router.post("/{provider}/test")
def test_cloud(provider: str, db: Session = Depends(get_db), principal: Principal = Depends(manage_clouds)):
    provider, _ = _provider(provider)
    item = _require_item(db, principal, provider)
    scope = str(_metadata(item).get("scope") or "")
    try:
        result = _test_payload(provider, _provider_request(provider, _decrypt(item), scope, resources=False))
    except CloudProviderError as error:
        record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="cloud.connection_test", outcome="failed", details={"provider": provider})
        db.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error
    record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="cloud.connection_test", details={"provider": provider})
    db.commit()
    return result


@router.get("/{provider}/resources")
def list_cloud_resources(provider: str, db: Session = Depends(get_db), principal: Principal = Depends(manage_clouds)):
    provider, _ = _provider(provider)
    item = _require_item(db, principal, provider)
    if not item.enabled:
        raise HTTPException(status_code=409, detail="Cloud está desativado")
    scope = str(_metadata(item).get("scope") or "")
    try:
        resources = _resource_payload(provider, _provider_request(provider, _decrypt(item), scope, resources=True))
    except CloudProviderError as error:
        record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="cloud.resources_listed", outcome="failed", details={"provider": provider})
        db.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error
    record(db, workspace_id=principal.workspace_id, actor=principal.actor, action="cloud.resources_listed", details={"provider": provider, "resource_count": len(resources)})
    db.commit()
    return {"provider": provider, "resources": resources}
