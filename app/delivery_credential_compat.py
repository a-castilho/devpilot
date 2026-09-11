from __future__ import annotations

import json

from sqlalchemy import case, select

from app.models import ProviderCredential
from app.services.vault import Vault


def _metadata(item: ProviderCredential) -> dict:
    try:
        value = json.loads(item.models or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def compatible_connection(db, workspace_id: str, provider: str) -> tuple[str, str] | None:
    """Resolve the credential from either cloud-admin or legacy delivery storage.

    The Cloud Admin screen stores `cloud:<provider>` + `cloud-admin`, while the
    older delivery subsystem stored `cloud-<provider>` + `Principal` with a JSON
    payload. Mandatory delivery must accept both so saving a key once is enough.
    """
    cloud_admin = f"cloud:{provider}"
    legacy = f"cloud-{provider}"
    rows = list(
        db.scalars(
            select(ProviderCredential)
            .where(
                ProviderCredential.workspace_id == workspace_id,
                ProviderCredential.provider.in_((cloud_admin, legacy)),
                ProviderCredential.enabled.is_(True),
            )
            .order_by(case((ProviderCredential.provider == cloud_admin, 0), else_=1), ProviderCredential.created_at.desc())
        ).all()
    )
    for item in rows:
        try:
            decrypted = Vault().decrypt(item.encrypted_secret)
        except ValueError:
            continue

        if item.provider == cloud_admin:
            token = str(decrypted or "").strip()
            scope = str(_metadata(item).get("scope") or "").strip()
            if token:
                return token, scope
            continue

        try:
            payload = json.loads(decrypted)
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            token = str(payload.get("token") or "").strip()
            account_id = str(payload.get("account_id") or "").strip()
        else:
            token = str(decrypted or "").strip()
            account_id = str(_metadata(item).get("scope") or "").strip()
        if token:
            return token, account_id
    return None


def install() -> None:
    # Import lazily here so this compatibility layer remains the single adapter
    # between the newer Cloud Admin vault and the older delivery implementation.
    from app import product_delivery_routes as delivery

    delivery.connection = compatible_connection


install()
