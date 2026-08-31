from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import cloud_admin_routes as cloud_admin
from app import product_delivery_routes as delivery
from app.config import get_settings
from app.models import ProviderCredential, Workspace
from app.services.vault import Vault


_CLOUD_ADMIN_LABEL = "cloud-admin"
_CLOUD_ADMIN_PREFIX = "cloud:"
_SCOPE_DISCOVERY_TIMEOUT = 10.0
_ORIGINAL_CONNECTION = delivery.connection
_ORIGINAL_REQUEST_JSON = delivery.request_json
_ORIGINAL_PROVISION_NEON = delivery.provision_neon
_ORIGINAL_PROVISION_RENDER = delivery.provision_render
_ORIGINAL_PROVISION_VERCEL = delivery.provision_vercel
_ORIGINAL_CLOUD_PROVIDER_REQUEST = cloud_admin._provider_request


def _cloud_admin_row(
    db: Session,
    workspace_id: str,
    provider: str,
) -> ProviderCredential | None:
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == f"{_CLOUD_ADMIN_PREFIX}{provider.strip().lower()}",
            ProviderCredential.label == _CLOUD_ADMIN_LABEL,
        )
    )


def _scope_candidates(provider: str, data: Any) -> list[str]:
    normalized = provider.strip().lower()
    source: list[Any] = []

    if normalized == "neon":
        if isinstance(data, list):
            source = data
        elif isinstance(data, dict):
            raw = data.get("organizations")
            if not isinstance(raw, list):
                raw = data.get("items")
            source = raw if isinstance(raw, list) else []
    elif normalized == "render":
        if isinstance(data, list):
            source = data
        elif isinstance(data, dict):
            raw = data.get("owners")
            source = raw if isinstance(raw, list) else []
    elif normalized == "vercel":
        if isinstance(data, dict):
            raw = data.get("teams")
            source = raw if isinstance(raw, list) else []
    else:
        return []

    candidates: list[str] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        raw = item
        if normalized == "neon" and isinstance(item.get("organization"), dict):
            raw = item["organization"]
        elif normalized == "render" and isinstance(item.get("owner"), dict):
            raw = item["owner"]

        value = str(
            raw.get("id")
            or raw.get("org_id")
            or raw.get("ownerId")
            or raw.get("owner_id")
            or ""
        ).strip()
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def _discover_scope(provider: str, token: str) -> str:
    """Resolve the account scope required for cloud operations from the API key."""
    normalized = provider.strip().lower()
    if normalized == "neon":
        url = "https://console.neon.tech/api/v2/users/me/organizations"
        params: dict[str, Any] | None = None
    elif normalized == "render":
        url = "https://api.render.com/v1/owners"
        params = {"limit": 100}
    elif normalized == "vercel":
        url = "https://api.vercel.com/v2/teams"
        params = {"limit": 100}
    else:
        return ""

    try:
        response = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "DevPilot-Cloud-Delivery/1.0",
            },
            params=params,
            timeout=_SCOPE_DISCOVERY_TIMEOUT,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return ""
    if response.status_code >= 400:
        return ""
    try:
        data = response.json()
    except ValueError:
        return ""

    candidates = _scope_candidates(normalized, data)
    return candidates[0] if len(candidates) == 1 else ""


def cloud_admin_connection(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    """Read a credential managed by Super Admin > Clouds without exposing it to the browser."""
    normalized = provider.strip().lower()
    item = _cloud_admin_row(db, workspace_id, normalized)
    if not item or not item.enabled:
        return None

    try:
        token = Vault().decrypt(item.encrypted_secret).strip()
    except (TypeError, ValueError):
        return None
    if not token:
        return None

    try:
        metadata = json.loads(item.models or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}

    scope = str(metadata.get("scope") or "").strip()
    if not scope and normalized in {"neon", "render", "vercel"}:
        scope = _discover_scope(normalized, token)
    return token, scope


def managed_trial_connection(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    """Use DevPilot's platform credential for an unconfigured trial workspace."""
    settings = get_settings()
    normalized = provider.strip().lower()
    if not settings.managed_trial_clouds_enabled:
        return None
    if normalized not in settings.managed_trial_providers:
        return None
    if _cloud_admin_row(db, workspace_id, normalized) is not None:
        return None

    platform = db.scalar(
        select(Workspace).where(Workspace.slug == settings.managed_trial_workspace_slug)
    )
    if not platform or platform.id == workspace_id:
        return None
    return cloud_admin_connection(db, platform.id, normalized)


def _connection_with_cloud_admin(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    current = cloud_admin_connection(db, workspace_id, provider)
    if current is not None:
        return current

    legacy = _ORIGINAL_CONNECTION(db, workspace_id, provider)
    if legacy is not None:
        return legacy

    return managed_trial_connection(db, workspace_id, provider)


def _cloud_admin_provider_request_with_scope(
    provider: str,
    secret: str,
    scope: str,
    *,
    resources: bool,
):
    normalized = provider.strip().lower()
    resolved_scope = scope.strip()
    if not resolved_scope and normalized in {"neon", "render", "vercel"}:
        resolved_scope = _discover_scope(normalized, secret)
    return _ORIGINAL_CLOUD_PROVIDER_REQUEST(
        provider,
        secret,
        resolved_scope,
        resources=resources,
    )


def _error_status(error: RuntimeError) -> int:
    match = re.search(r"\bHTTP\s+(\d{3})\b", str(error))
    return int(match.group(1)) if match else 0


def _request_json_with_cloud_scope(
    client,
    provider: str,
    method: str,
    url: str,
    token: str,
    *,
    payload: Any | None = None,
    params: dict[str, Any] | None = None,
):
    normalized_provider = provider.strip().lower()
    normalized_params = dict(params) if isinstance(params, dict) else params
    normalized_payload = payload

    if normalized_provider == "vercel" and isinstance(normalized_params, dict):
        scope = str(normalized_params.get("teamId") or "").strip()
        if scope and not scope.startswith("team_"):
            normalized_params.pop("teamId", None)
            normalized_params["slug"] = scope

    if (
        normalized_provider == "neon"
        and method.upper() == "POST"
        and url.rstrip("/").endswith("/projects")
        and isinstance(payload, dict)
        and isinstance(payload.get("project"), dict)
    ):
        project_payload = dict(payload["project"])
        org_id = str(project_payload.pop("org_id", "") or "").strip()
        normalized_payload = dict(payload)
        normalized_payload["project"] = project_payload
        if org_id:
            if not isinstance(normalized_params, dict):
                normalized_params = {}
            normalized_params["org_id"] = org_id

    attempts = 6 if normalized_provider == "neon" else 1
    for attempt in range(attempts):
        try:
            return _ORIGINAL_REQUEST_JSON(
                client,
                provider,
                method,
                url,
                token,
                payload=normalized_payload,
                params=normalized_params,
            )
        except RuntimeError as error:
            status = _error_status(error)
            if normalized_provider != "neon" or status not in {423, 503} or attempt >= attempts - 1:
                raise
            time.sleep(min(0.5 * (2**attempt), 3.0))
    return None


def _optional_request_json(
    client,
    provider: str,
    method: str,
    url: str,
    token: str,
    *,
    payload: Any | None = None,
    params: dict[str, Any] | None = None,
):
    try:
        return _request_json_with_cloud_scope(
            client,
            provider,
            method,
            url,
            token,
            payload=payload,
            params=params,
        )
    except RuntimeError as error:
        if _error_status(error) == 404:
            return None
        raise


def _items(data: Any, key: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    value = data.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _neon_existing_project(
    client,
    token: str,
    account_id: str,
    project_name: str,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {"limit": 100, "search": project_name}
    if account_id:
        params["org_id"] = account_id
    data = _request_json_with_cloud_scope(
        client,
        "neon",
        "GET",
        f"{delivery.NEON_API}/projects",
        token,
        params=params,
    ) or {}
    exact = [item for item in _items(data, "projects") if str(item.get("name") or "") == project_name]
    if not exact:
        return None
    exact.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return exact[0]


def _hydrate_existing_neon(
    client,
    token: str,
    project_data: dict[str, Any],
    state: dict[str, Any],
) -> None:
    project_id = str(project_data.get("id") or "").strip()
    if not project_id:
        return
    neon = state.setdefault("providers", {}).setdefault("neon", {})
    neon["project_id"] = project_id
    neon["reused"] = True

    branches_data = _request_json_with_cloud_scope(
        client,
        "neon",
        "GET",
        f"{delivery.NEON_API}/projects/{project_id}/branches",
        token,
        params={"limit": 100},
    ) or {}
    branches = _items(branches_data, "branches")
    if not branches:
        return

    main = next((item for item in branches if str(item.get("name") or "") == "main"), None)
    if main is None:
        main = next((item for item in branches if item.get("default") or item.get("primary")), branches[0])
    homolog = next((item for item in branches if str(item.get("name") or "") == "homolog"), None)

    main_branch_id = str(main.get("id") or "").strip()
    if main_branch_id:
        neon["main_branch_id"] = main_branch_id
    if homolog:
        homolog_branch_id = str(homolog.get("id") or "").strip()
        if homolog_branch_id:
            neon["homolog_branch_id"] = homolog_branch_id

    if not main_branch_id:
        return

    databases_data = _request_json_with_cloud_scope(
        client,
        "neon",
        "GET",
        f"{delivery.NEON_API}/projects/{project_id}/branches/{main_branch_id}/databases",
        token,
    ) or {}
    databases = _items(databases_data, "databases")
    if databases:
        preferred = next((item for item in databases if str(item.get("name") or "") == "app"), databases[0])
        database_name = str(preferred.get("name") or "").strip()
        if database_name:
            neon["database_name"] = database_name

    roles_data = _request_json_with_cloud_scope(
        client,
        "neon",
        "GET",
        f"{delivery.NEON_API}/projects/{project_id}/branches/{main_branch_id}/roles",
        token,
    ) or {}
    roles = _items(roles_data, "roles")
    if roles:
        preferred_role = next((item for item in roles if str(item.get("name") or "") == "app"), None)
        if preferred_role is None:
            preferred_role = next((item for item in roles if not item.get("protected")), roles[0])
        role_name = str(preferred_role.get("name") or "").strip()
        if role_name:
            neon["role_name"] = role_name


def _provision_neon_reconciled(
    client,
    token: str,
    account_id: str,
    project,
    state: dict[str, Any],
) -> str:
    neon = state.setdefault("providers", {}).setdefault("neon", {})
    if not neon.get("project_id"):
        existing = _neon_existing_project(client, token, account_id, project.slug)
        if existing:
            _hydrate_existing_neon(client, token, existing, state)
    return _ORIGINAL_PROVISION_NEON(client, token, account_id, project, state)


def _render_service(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    service = raw.get("service")
    return service if isinstance(service, dict) else raw


def _hydrate_existing_render(
    client,
    token: str,
    account_id: str,
    project_name: str,
    state: dict[str, Any],
) -> None:
    params: dict[str, Any] = {"limit": 100, "name": project_name}
    if account_id:
        params["ownerId"] = account_id
    data = _request_json_with_cloud_scope(
        client,
        "render",
        "GET",
        f"{delivery.RENDER_API}/services",
        token,
        params=params,
    ) or []
    source = data if isinstance(data, list) else []
    matches = []
    for wrapper in source:
        service = _render_service(wrapper)
        if str(service.get("name") or "") == project_name:
            matches.append(service)
    if not matches:
        return
    matches.sort(key=lambda item: str(item.get("createdAt") or item.get("created_at") or ""), reverse=True)
    service = matches[0]
    service_id = str(service.get("id") or "").strip()
    details = service.get("serviceDetails") if isinstance(service.get("serviceDetails"), dict) else {}
    url = str(details.get("url") or service.get("url") or "").strip()
    if service_id and not url:
        detail = _optional_request_json(
            client,
            "render",
            "GET",
            f"{delivery.RENDER_API}/services/{service_id}",
            token,
        ) or {}
        detail_service = _render_service(detail)
        detail_details = (
            detail_service.get("serviceDetails")
            if isinstance(detail_service.get("serviceDetails"), dict)
            else {}
        )
        url = str(detail_details.get("url") or detail_service.get("url") or "").strip()
    if service_id and url:
        render = state.setdefault("providers", {}).setdefault("render", {})
        render.update({"service_id": service_id, "url": url, "status": "provisioned", "reused": True})


def _provision_render_reconciled(
    client,
    token: str,
    account_id: str,
    project,
    state: dict[str, Any],
    database_url: str | None,
) -> str:
    render = state.setdefault("providers", {}).setdefault("render", {})
    if not render.get("service_id") or not render.get("url"):
        _hydrate_existing_render(client, token, account_id, f"{project.slug}-homolog", state)
    return _ORIGINAL_PROVISION_RENDER(client, token, account_id, project, state, database_url)


def _provision_vercel_reconciled(
    client,
    token: str,
    account_id: str,
    project,
    state: dict[str, Any],
    backend_url: str | None,
    repo_full_name: str,
) -> str:
    vercel = state.setdefault("providers", {}).setdefault("vercel", {})
    if not vercel.get("project_id"):
        params = {"teamId": account_id} if account_id else None
        existing = _optional_request_json(
            client,
            "vercel",
            "GET",
            f"{delivery.VERCEL_API}/v9/projects/{project.slug}",
            token,
            params=params,
        )
        if isinstance(existing, dict):
            project_id = str(existing.get("id") or "").strip()
            if project_id:
                vercel.update({"project_id": project_id, "reused": True})
    return _ORIGINAL_PROVISION_VERCEL(
        client,
        token,
        account_id,
        project,
        state,
        backend_url,
        repo_full_name,
    )


def install_delivery_cloud_bridge() -> None:
    """Make delivery idempotent and reuse credentials/resources managed by Super Admin."""
    if not getattr(delivery.connection, "_devpilot_cloud_admin_bridge", False):
        setattr(_connection_with_cloud_admin, "_devpilot_cloud_admin_bridge", True)
        delivery.connection = _connection_with_cloud_admin
    if not getattr(delivery.request_json, "_devpilot_cloud_scope_bridge", False):
        setattr(_request_json_with_cloud_scope, "_devpilot_cloud_scope_bridge", True)
        delivery.request_json = _request_json_with_cloud_scope
    if not getattr(delivery.provision_neon, "_devpilot_cloud_reconcile", False):
        setattr(_provision_neon_reconciled, "_devpilot_cloud_reconcile", True)
        delivery.provision_neon = _provision_neon_reconciled
    if not getattr(delivery.provision_render, "_devpilot_cloud_reconcile", False):
        setattr(_provision_render_reconciled, "_devpilot_cloud_reconcile", True)
        delivery.provision_render = _provision_render_reconciled
    if not getattr(delivery.provision_vercel, "_devpilot_cloud_reconcile", False):
        setattr(_provision_vercel_reconciled, "_devpilot_cloud_reconcile", True)
        delivery.provision_vercel = _provision_vercel_reconciled
    if not getattr(cloud_admin._provider_request, "_devpilot_cloud_scope_bridge", False):
        setattr(_cloud_admin_provider_request_with_scope, "_devpilot_cloud_scope_bridge", True)
        cloud_admin._provider_request = _cloud_admin_provider_request_with_scope
