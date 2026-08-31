from __future__ import annotations

import json
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
    """Resolve the account scope required for create operations from the API key.

    Neon personal API keys need ``org_id`` for organization projects and Render
    requires ``ownerId`` when creating a service. The Cloud Admin form allows the
    scope field to be empty, so delivery must be able to derive the single
    accessible organization/workspace from the token itself.
    """
    normalized = provider.strip().lower()
    if normalized == "neon":
        url = "https://console.neon.tech/api/v2/users/me/organizations"
        params: dict[str, Any] | None = None
    elif normalized == "render":
        url = "https://api.render.com/v1/owners"
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
    if not scope and normalized in {"neon", "render"}:
        scope = _discover_scope(normalized, token)
    return token, scope


def managed_trial_connection(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    """Use DevPilot's platform credential for an unconfigured trial workspace.

    Trial users never receive the token. The credential remains encrypted in the
    platform workspace and is consumed only by the backend. A workspace that has
    its own Cloud Admin row is considered self-managed, even when that row is
    intentionally disabled, so an explicit customer configuration is never
    silently replaced by DevPilot's credential.
    """
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
    # 1. A purchased/self-managed installation or workspace always wins.
    current = cloud_admin_connection(db, workspace_id, provider)
    if current is not None:
        return current

    # 2. Preserve the legacy local credential format while older installations migrate.
    legacy = _ORIGINAL_CONNECTION(db, workspace_id, provider)
    if legacy is not None:
        return legacy

    # 3. Trial workspaces get the frictionless DevPilot-managed experience.
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
    if not resolved_scope and normalized in {"neon", "render"}:
        resolved_scope = _discover_scope(normalized, secret)
    return _ORIGINAL_CLOUD_PROVIDER_REQUEST(
        provider,
        secret,
        resolved_scope,
        resources=resources,
    )


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

    # Neon expects org_id as a request parameter when a personal API key is
    # used. The original delivery flow put org_id inside the nested project
    # object, which Neon rejects with HTTP 400.
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

    return _ORIGINAL_REQUEST_JSON(
        client,
        provider,
        method,
        url,
        token,
        payload=normalized_payload,
        params=normalized_params,
    )


def install_delivery_cloud_bridge() -> None:
    """Make product delivery consume self-managed or DevPilot-managed cloud credentials."""
    if not getattr(delivery.connection, "_devpilot_cloud_admin_bridge", False):
        setattr(_connection_with_cloud_admin, "_devpilot_cloud_admin_bridge", True)
        delivery.connection = _connection_with_cloud_admin
    if not getattr(delivery.request_json, "_devpilot_cloud_scope_bridge", False):
        setattr(_request_json_with_cloud_scope, "_devpilot_cloud_scope_bridge", True)
        delivery.request_json = _request_json_with_cloud_scope
    if not getattr(cloud_admin._provider_request, "_devpilot_cloud_scope_bridge", False):
        setattr(_cloud_admin_provider_request_with_scope, "_devpilot_cloud_scope_bridge", True)
        cloud_admin._provider_request = _cloud_admin_provider_request_with_scope
