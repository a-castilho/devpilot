from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import product_delivery_routes as delivery
from app.models import ProviderCredential
from app.services.vault import Vault


_CLOUD_ADMIN_LABEL = "cloud-admin"
_CLOUD_ADMIN_PREFIX = "cloud:"
_ORIGINAL_CONNECTION = delivery.connection
_ORIGINAL_REQUEST_JSON = delivery.request_json


def cloud_admin_connection(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    """Read the credential already managed by Super Admin > Clouds.

    Cloud Admin stores the secret directly and keeps the provider scope in the
    credential metadata. Product delivery historically used a different storage
    key and JSON payload, which made configured clouds appear missing.
    """
    item = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == f"{_CLOUD_ADMIN_PREFIX}{provider.strip().lower()}",
            ProviderCredential.label == _CLOUD_ADMIN_LABEL,
            ProviderCredential.enabled.is_(True),
        )
    )
    if not item:
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


def _connection_with_cloud_admin(
    db: Session,
    workspace_id: str,
    provider: str,
) -> tuple[str, str] | None:
    current = cloud_admin_connection(db, workspace_id, provider)
    if current is not None:
        return current
    return _ORIGINAL_CONNECTION(db, workspace_id, provider)


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
    """Make product delivery consume the canonical Cloud Admin credentials."""
    if not getattr(delivery.connection, "_devpilot_cloud_admin_bridge", False):
        setattr(_connection_with_cloud_admin, "_devpilot_cloud_admin_bridge", True)
        delivery.connection = _connection_with_cloud_admin
    if not getattr(delivery.request_json, "_devpilot_cloud_scope_bridge", False):
        setattr(_request_json_with_cloud_scope, "_devpilot_cloud_scope_bridge", True)
        delivery.request_json = _request_json_with_cloud_scope
