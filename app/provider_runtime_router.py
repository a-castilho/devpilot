from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential, Workspace
from app.security import require_access
from app.services.audit import record
from app.services.provider_runtime import ProviderRuntimeError, run_provider_connection_test
from app.services.vault import Vault


router = APIRouter(prefix="/api/providers", dependencies=[Depends(require_access)])


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def _models(item: ProviderCredential) -> list[str]:
    try:
        values = json.loads(item.models or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


@router.post("/{provider_id}/test")
def test_saved_provider(
    provider_id: str,
    model: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
):
    """Execute a tiny real model call using an encrypted saved credential.

    The request uses a fixed harmless prompt and a very small output budget. Credentials and raw
    provider error bodies never leave the server or enter the audit trail.
    """

    ws = _workspace(db)
    item = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == provider_id,
            ProviderCredential.workspace_id == ws.id,
        )
    )
    if not item:
        raise HTTPException(404, "Conexão de IA não encontrada.")
    if not item.enabled:
        raise HTTPException(409, "A conexão de IA está pausada.")

    configured_models = _models(item)
    selected_model = (model or (configured_models[0] if configured_models else "")).strip()
    if not selected_model:
        raise HTTPException(422, "A conexão não possui um modelo configurado.")
    if model and selected_model not in configured_models:
        raise HTTPException(422, "O modelo solicitado não pertence a esta conexão.")

    try:
        result = run_provider_connection_test(
            item.provider,
            Vault().decrypt(item.encrypted_secret),
            selected_model,
        )
    except (ProviderRuntimeError, ValueError) as error:
        record(
            db,
            workspace_id=ws.id,
            actor="owner",
            action="provider.tested",
            outcome="failed",
            details={
                "provider": item.provider,
                "connection_id": item.id,
                "model": selected_model,
            },
        )
        db.commit()
        raise HTTPException(422, str(error)) from error

    record(
        db,
        workspace_id=ws.id,
        actor="owner",
        action="provider.tested",
        details={
            "provider": item.provider,
            "connection_id": item.id,
            "model": result.model,
            "latency_ms": result.latency_ms,
        },
    )
    db.commit()
    return {
        "ok": True,
        "connection_id": item.id,
        "label": item.label,
        **result.to_dict(),
    }
