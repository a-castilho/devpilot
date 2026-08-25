from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import product_delivery_routes as delivery
from app.config import get_settings
from app.models import ProviderCredential, Workspace
from app.services.vault import Vault


_CLOUD_ADMIN_LABEL = "cloud-admin"
_CLOUD_ADMIN_PREFIX = "cloud:"
_ORIGINAL_CONNECTION = delivery.connection
_ORIGINAL_REQUEST_JSON = delivery.request_json


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


def cloud_admin_connection(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    """Read a credential managed by Super Admin > Clouds without exposing it to the browser."""
    item = _cloud_admin_row(db, workspace_id, provider)
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
    return token, str(metadata.get("scope") or "").strip()


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
    normalized = dict(params) if isinstance(params, dict) else params
    if provider == "vercel" and isinstance(normalized, dict):
        scope = str(normalized.get("teamId") or "").strip()
        if scope and not scope.startswith("team_"):
            normalized.pop("teamId", None)
            normalized["slug"] = scope
    return _ORIGINAL_REQUEST_JSON(
        client,
        provider,
        method,
        url,
        token,
        payload=payload,
        params=normalized,
    )


def install_delivery_cloud_bridge() -> None:
    """Make product delivery consume self-managed or DevPilot-managed cloud credentials."""
    if not getattr(delivery.connection, "_devpilot_cloud_admin_bridge", False):
        setattr(_connection_with_cloud_admin, "_devpilot_cloud_admin_bridge", True)
        delivery.connection = _connection_with_cloud_admin
    if not getattr(delivery.request_json, "_devpilot_cloud_scope_bridge", False):
        setattr(_request_json_with_cloud_scope, "_devpilot_cloud_scope_bridge", True)
        delivery.request_json = _request_json_with_cloud_scope
