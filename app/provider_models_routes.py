from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential
from app.security import Principal, require_access, session_principal
from app.services.audit import record
from app.services.provider_models import (
    REFERENCE_CATALOG_DATE,
    SUPPORTED_MODEL_PROVIDERS,
    ProviderModel,
    ProviderModelDiscoveryError,
    discover_provider_models,
    recommended_provider_models,
    reference_provider_models,
)
from app.services.vault import Vault
from app.services.workspace_scope import workspace_for_principal

router = APIRouter(prefix="/api/providers", dependencies=[Depends(require_access)])


class ProviderDiscoveryRequest(BaseModel):
    provider: str = Field(pattern=r"^(openai|anthropic|google)$")
    api_key: str = Field(min_length=8, max_length=10_000)


class ProviderConnectRequest(BaseModel):
    provider: str = Field(pattern=r"^(openai|anthropic|google|custom)$")
    label: str = Field(min_length=2, max_length=100)
    api_key: str = Field(min_length=8, max_length=10_000)
    models: list[str] = Field(default_factory=list, max_length=500)


class ProviderEnabledRequest(BaseModel):
    enabled: bool


class ProviderModelsUpdateRequest(BaseModel):
    models: list[str] = Field(min_length=1, max_length=500)


def stored_models(item: ProviderCredential | None) -> list[str]:
    if not item:
        return []
    try:
        values = json.loads(item.models or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(value).strip() for value in values if str(value).strip()] if isinstance(values, list) else []


def normalize_model_ids(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def model_payload(models: list[ProviderModel]) -> list[dict[str, str]]:
    return [model.to_dict() for model in models]


def stored_model_objects(item: ProviderCredential | None) -> list[ProviderModel]:
    return [ProviderModel(id=value, label=value) for value in stored_models(item)]


def recommended_payload(provider: str, models: list[ProviderModel]) -> list[dict[str, str]]:
    return model_payload(recommended_provider_models(provider, models))


def credential(db: Session, workspace_id: str, connection_id: str) -> ProviderCredential:
    item = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == connection_id,
            ProviderCredential.workspace_id == workspace_id,
        )
    )
    if not item:
        raise HTTPException(404, "Conexão de IA não encontrada")
    return item


def decrypt_credential(item: ProviderCredential) -> str:
    try:
        return Vault().decrypt(item.encrypted_secret)
    except ValueError as error:
        raise ProviderModelDiscoveryError("A credencial salva não pôde ser validada.") from error


@router.get("/model-catalog")
def model_catalog(
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    ws = workspace_for_principal(db, principal)
    items = db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == ws.id,
            ProviderCredential.enabled.is_(True),
        )
        .order_by(ProviderCredential.created_at.desc())
    ).all()
    latest: dict[str, ProviderCredential] = {}
    for item in items:
        if item.provider in SUPPORTED_MODEL_PROVIDERS:
            latest.setdefault(item.provider, item)

    providers = {}
    for provider in sorted(SUPPORTED_MODEL_PROVIDERS):
        item = latest.get(provider)
        stored = stored_model_objects(item)
        source_models = stored or reference_provider_models(provider)
        providers[provider] = {
            "provider": provider,
            "source": "stored" if stored else "reference",
            "models": model_payload(source_models),
            "recommended_models": recommended_payload(provider, source_models),
            "connection_id": item.id if item else None,
            "reference_catalog_date": REFERENCE_CATALOG_DATE,
            "warning": "",
        }
    providers["custom"] = {
        "provider": "custom",
        "source": "manual",
        "models": [],
        "recommended_models": [],
        "connection_id": None,
        "reference_catalog_date": REFERENCE_CATALOG_DATE,
        "warning": "Provedores customizados usam catálogo manual.",
    }
    return {
        "refreshed_at": datetime.now(timezone.utc),
        "reference_catalog_date": REFERENCE_CATALOG_DATE,
        "providers": providers,
    }


@router.post("/model-catalog/refresh")
def refresh_model_catalog(
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_access),
):
    """Refresh available catalogs without overwriting the user's selected model set."""
    ws = workspace_for_principal(db, principal)
    items = db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == ws.id,
            ProviderCredential.enabled.is_(True),
            ProviderCredential.provider.in_(SUPPORTED_MODEL_PROVIDERS),
        )
        .order_by(ProviderCredential.created_at.desc())
    ).all()
    latest: dict[str, ProviderCredential] = {}
    for item in items:
        latest.setdefault(item.provider, item)

    refreshed = {}
    for provider, item in latest.items():
        selected = stored_models(item)
        try:
            models = discover_provider_models(provider, decrypt_credential(item))
        except ProviderModelDiscoveryError as error:
            fallback = stored_model_objects(item)
            refreshed[provider] = {
                "provider": provider,
                "source": "stored",
                "models": model_payload(fallback),
                "selected_models": selected,
                "recommended_models": recommended_payload(provider, fallback),
                "connection_id": item.id,
                "warning": str(error),
            }
            continue

        refreshed[provider] = {
            "provider": provider,
            "source": "live",
            "models": model_payload(models),
            "selected_models": selected,
            "recommended_models": recommended_payload(provider, models),
            "connection_id": item.id,
            "warning": "",
        }
        record(
            db,
            workspace_id=ws.id,
            actor=actor,
            action="provider.models_refreshed",
            details={
                "provider": provider,
                "connection_id": item.id,
                "available_count": len(models),
                "selected_count": len(selected),
            },
        )
    db.commit()
    return {"refreshed_at": datetime.now(timezone.utc), "providers": refreshed}


@router.post("/discover-models")
def discover_models(
    payload: ProviderDiscoveryRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_access),
):
    ws = workspace_for_principal(db, principal)
    try:
        models = discover_provider_models(payload.provider, payload.api_key)
    except ProviderModelDiscoveryError as error:
        record(
            db,
            workspace_id=ws.id,
            actor=actor,
            action="provider.models_discovery",
            outcome="failed",
            details={"provider": payload.provider},
        )
        db.commit()
        raise HTTPException(422, str(error)) from error
    recommended = recommended_provider_models(payload.provider, models)
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="provider.models_discovery",
        details={
            "provider": payload.provider,
            "available_count": len(models),
            "recommended_count": len(recommended),
        },
    )
    db.commit()
    return {
        "provider": payload.provider,
        "source": "live",
        "models": model_payload(models),
        "recommended_models": model_payload(recommended),
        "refreshed_at": datetime.now(timezone.utc),
    }


@router.post("/connect", status_code=201)
def connect_provider(
    payload: ProviderConnectRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_access),
):
    ws = workspace_for_principal(db, principal)
    provider = payload.provider.strip().lower()
    models = normalize_model_ids(payload.models)
    if provider in SUPPORTED_MODEL_PROVIDERS:
        try:
            discovered = discover_provider_models(provider, payload.api_key)
        except ProviderModelDiscoveryError as error:
            raise HTTPException(422, str(error)) from error
        available = {model.id for model in discovered}
        unavailable = sorted(set(models) - available)
        if unavailable:
            raise HTTPException(
                422,
                f"Modelos não disponíveis para esta chave: {', '.join(unavailable[:5])}",
            )
        if not models:
            models = [model.id for model in recommended_provider_models(provider, discovered)]
    elif not models:
        raise HTTPException(422, "Informe ao menos um modelo para o provedor customizado.")

    item = ProviderCredential(
        workspace_id=ws.id,
        provider=provider,
        label=payload.label.strip(),
        encrypted_secret=Vault().encrypt(payload.api_key.strip()),
        models=json.dumps(models),
        enabled=True,
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="provider.created",
        details={"provider": item.provider, "label": item.label, "model_count": len(models)},
    )
    db.commit()
    return {
        "id": item.id,
        "provider": item.provider,
        "label": item.label,
        "models": models,
        "enabled": item.enabled,
        "created_at": item.created_at,
    }


@router.get("/{connection_id}/models")
def connection_models(
    connection_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
):
    """Return selected models plus safe available options; credentials never leave the server."""
    ws = workspace_for_principal(db, principal)
    item = credential(db, ws.id, connection_id)
    selected = stored_models(item)

    if item.provider not in SUPPORTED_MODEL_PROVIDERS:
        models = stored_model_objects(item)
        return {
            "id": item.id,
            "provider": item.provider,
            "source": "manual",
            "models": model_payload(models),
            "selected_models": selected,
            "recommended_models": model_payload(models[:6]),
            "warning": "",
        }

    try:
        available = discover_provider_models(item.provider, decrypt_credential(item))
        source = "live"
        warning = ""
    except ProviderModelDiscoveryError as error:
        available = stored_model_objects(item)
        source = "stored"
        warning = str(error)

    return {
        "id": item.id,
        "provider": item.provider,
        "source": source,
        "models": model_payload(available),
        "selected_models": selected,
        "recommended_models": recommended_payload(item.provider, available),
        "warning": warning,
    }


@router.patch("/{connection_id}/models")
def update_connection_models(
    connection_id: str,
    payload: ProviderModelsUpdateRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_access),
):
    ws = workspace_for_principal(db, principal)
    item = credential(db, ws.id, connection_id)
    models = normalize_model_ids(payload.models)
    if not models:
        raise HTTPException(422, "Selecione ao menos um modelo para esta conexão.")

    validation_source = "manual"
    warning = ""
    if item.provider in SUPPORTED_MODEL_PROVIDERS:
        try:
            available_models = discover_provider_models(item.provider, decrypt_credential(item))
            available = {model.id for model in available_models}
            unavailable = sorted(set(models) - available)
            if unavailable:
                raise HTTPException(
                    422,
                    f"Modelos não disponíveis para esta credencial: {', '.join(unavailable[:5])}",
                )
            validation_source = "live"
        except ProviderModelDiscoveryError as error:
            existing = set(stored_models(item))
            if not set(models).issubset(existing):
                raise HTTPException(
                    422,
                    "Não foi possível validar modelos novos agora. "
                    "Você ainda pode reduzir a seleção usando os modelos já salvos.",
                ) from error
            validation_source = "stored"
            warning = str(error)

    item.models = json.dumps(models)
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="provider.models_updated",
        details={
            "connection_id": item.id,
            "provider": item.provider,
            "model_count": len(models),
            "validation_source": validation_source,
        },
    )
    db.commit()
    return {
        "id": item.id,
        "provider": item.provider,
        "models": models,
        "model_count": len(models),
        "validation_source": validation_source,
        "warning": warning,
    }


@router.patch("/{connection_id}/enabled")
def set_provider_enabled(
    connection_id: str,
    payload: ProviderEnabledRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_access),
):
    ws = workspace_for_principal(db, principal)
    item = credential(db, ws.id, connection_id)
    item.enabled = payload.enabled
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="provider.enabled_changed",
        details={"connection_id": item.id, "provider": item.provider, "enabled": item.enabled},
    )
    db.commit()
    return {"id": item.id, "enabled": item.enabled}


@router.delete("/{connection_id}", status_code=204)
def delete_provider(
    connection_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_access),
):
    ws = workspace_for_principal(db, principal)
    item = credential(db, ws.id, connection_id)
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="provider.deleted",
        details={"connection_id": item.id, "provider": item.provider, "label": item.label},
    )
    db.delete(item)
    db.commit()
    return None
