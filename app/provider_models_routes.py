from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential, Workspace
from app.security import require_access
from app.services.audit import record
from app.services.provider_models import (
    REFERENCE_CATALOG_DATE,
    SUPPORTED_MODEL_PROVIDERS,
    ProviderModelDiscoveryError,
    discover_provider_models,
    reference_provider_models,
)
from app.services.vault import Vault

router = APIRouter(prefix="/api/providers", dependencies=[Depends(require_access)])


class ProviderDiscoveryRequest(BaseModel):
    provider: str = Field(pattern=r"^(openai|anthropic|google)$")
    api_key: str = Field(min_length=8, max_length=10_000)


class ProviderConnectRequest(BaseModel):
    provider: str = Field(pattern=r"^(openai|anthropic|google|custom)$")
    label: str = Field(min_length=2, max_length=100)
    api_key: str = Field(min_length=8, max_length=10_000)
    models: list[str] = Field(default_factory=list)


class ProviderEnabledRequest(BaseModel):
    enabled: bool


def workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def stored_models(item: ProviderCredential | None) -> list[str]:
    if not item:
        return []
    try:
        values = json.loads(item.models or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(value).strip() for value in values if str(value).strip()] if isinstance(values, list) else []


def model_payload(models) -> list[dict[str, str]]:
    return [model.to_dict() for model in models]


def credential(db: Session, workspace_id: str, connection_id: str) -> ProviderCredential:
    item = db.scalar(select(ProviderCredential).where(
        ProviderCredential.id == connection_id,
        ProviderCredential.workspace_id == workspace_id,
    ))
    if not item:
        raise HTTPException(404, "Conexão de IA não encontrada")
    return item


@router.get("/model-catalog")
def model_catalog(db: Session = Depends(get_db)):
    ws = workspace(db)
    items = db.scalars(select(ProviderCredential).where(
        ProviderCredential.workspace_id == ws.id,
        ProviderCredential.enabled.is_(True),
    ).order_by(ProviderCredential.created_at.desc())).all()
    latest: dict[str, ProviderCredential] = {}
    for item in items:
        if item.provider in SUPPORTED_MODEL_PROVIDERS:
            latest.setdefault(item.provider, item)

    providers = {}
    for provider in sorted(SUPPORTED_MODEL_PROVIDERS):
        item = latest.get(provider)
        stored = stored_models(item)
        providers[provider] = {
            "provider": provider,
            "source": "stored" if stored else "reference",
            "models": ([{"id": value, "label": value} for value in stored]
                       if stored else model_payload(reference_provider_models(provider))),
            "connection_id": item.id if item else None,
            "reference_catalog_date": REFERENCE_CATALOG_DATE,
            "warning": "",
        }
    providers["custom"] = {
        "provider": "custom", "source": "manual", "models": [], "connection_id": None,
        "reference_catalog_date": REFERENCE_CATALOG_DATE,
        "warning": "Provedores customizados usam catálogo manual.",
    }
    return {"refreshed_at": datetime.now(timezone.utc),
            "reference_catalog_date": REFERENCE_CATALOG_DATE, "providers": providers}


@router.post("/model-catalog/refresh")
def refresh_model_catalog(db: Session = Depends(get_db), actor: str = Depends(require_access)):
    ws = workspace(db)
    items = db.scalars(select(ProviderCredential).where(
        ProviderCredential.workspace_id == ws.id,
        ProviderCredential.enabled.is_(True),
        ProviderCredential.provider.in_(SUPPORTED_MODEL_PROVIDERS),
    ).order_by(ProviderCredential.created_at.desc())).all()
    latest: dict[str, ProviderCredential] = {}
    for item in items:
        latest.setdefault(item.provider, item)

    refreshed = {}
    for provider, item in latest.items():
        try:
            models = discover_provider_models(provider, Vault().decrypt(item.encrypted_secret))
        except (ProviderModelDiscoveryError, ValueError) as error:
            refreshed[provider] = {
                "provider": provider, "source": "stored",
                "models": [{"id": value, "label": value} for value in stored_models(item)],
                "connection_id": item.id, "warning": str(error),
            }
            continue
        item.models = json.dumps([model.id for model in models])
        refreshed[provider] = {"provider": provider, "source": "live",
                               "models": model_payload(models), "connection_id": item.id,
                               "warning": ""}
        record(db, workspace_id=ws.id, actor=actor, action="provider.models_refreshed",
               details={"provider": provider, "connection_id": item.id, "count": len(models)})
    db.commit()
    return {"refreshed_at": datetime.now(timezone.utc), "providers": refreshed}


@router.post("/discover-models")
def discover_models(payload: ProviderDiscoveryRequest, db: Session = Depends(get_db),
                    actor: str = Depends(require_access)):
    ws = workspace(db)
    try:
        models = discover_provider_models(payload.provider, payload.api_key)
    except ProviderModelDiscoveryError as error:
        record(db, workspace_id=ws.id, actor=actor, action="provider.models_discovery",
               outcome="failed", details={"provider": payload.provider})
        db.commit()
        raise HTTPException(422, str(error)) from error
    record(db, workspace_id=ws.id, actor=actor, action="provider.models_discovery",
           details={"provider": payload.provider, "count": len(models)})
    db.commit()
    return {"provider": payload.provider, "source": "live", "models": model_payload(models),
            "refreshed_at": datetime.now(timezone.utc)}


@router.post("/connect", status_code=201)
def connect_provider(payload: ProviderConnectRequest, db: Session = Depends(get_db),
                     actor: str = Depends(require_access)):
    ws = workspace(db)
    provider = payload.provider.strip().lower()
    models = list(dict.fromkeys(value.strip() for value in payload.models if value.strip()))
    if provider in SUPPORTED_MODEL_PROVIDERS:
        try:
            discovered = discover_provider_models(provider, payload.api_key)
        except ProviderModelDiscoveryError as error:
            raise HTTPException(422, str(error)) from error
        available = {model.id for model in discovered}
        unavailable = sorted(set(models) - available)
        if unavailable:
            raise HTTPException(422, f"Modelos não disponíveis para esta chave: {', '.join(unavailable[:5])}")
        if not models:
            models = [model.id for model in discovered]

    item = ProviderCredential(workspace_id=ws.id, provider=provider, label=payload.label.strip(),
                              encrypted_secret=Vault().encrypt(payload.api_key.strip()),
                              models=json.dumps(models), enabled=True)
    db.add(item)
    db.flush()
    record(db, workspace_id=ws.id, actor=actor, action="provider.created",
           details={"provider": item.provider, "label": item.label, "model_count": len(models)})
    db.commit()
    return {"id": item.id, "provider": item.provider, "label": item.label, "models": models,
            "enabled": item.enabled, "created_at": item.created_at}


@router.patch("/{connection_id}/enabled")
def set_provider_enabled(connection_id: str, payload: ProviderEnabledRequest,
                         db: Session = Depends(get_db), actor: str = Depends(require_access)):
    ws = workspace(db)
    item = credential(db, ws.id, connection_id)
    item.enabled = payload.enabled
    record(db, workspace_id=ws.id, actor=actor, action="provider.enabled_changed",
           details={"connection_id": item.id, "provider": item.provider, "enabled": item.enabled})
    db.commit()
    return {"id": item.id, "enabled": item.enabled}


@router.delete("/{connection_id}", status_code=204)
def delete_provider(connection_id: str, db: Session = Depends(get_db),
                    actor: str = Depends(require_access)):
    ws = workspace(db)
    item = credential(db, ws.id, connection_id)
    record(db, workspace_id=ws.id, actor=actor, action="provider.deleted",
           details={"connection_id": item.id, "provider": item.provider, "label": item.label})
    db.delete(item)
    db.commit()
    return None
