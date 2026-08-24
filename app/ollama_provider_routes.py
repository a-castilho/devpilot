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
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError
from app.services.vault import Vault


router = APIRouter(prefix="/api/ollama-provider", dependencies=[Depends(require_access)])
REFERENCE_MODELS = ("tinyllama", "phi3:mini")


class OllamaConnectRequest(BaseModel):
    label: str = Field(min_length=2, max_length=100)
    models: list[str] = Field(default_factory=list, max_length=50)


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if item:
        return item
    item = Workspace(name="DevPilot", slug="default")
    db.add(item)
    db.flush()
    return item


def _normalize_models(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _ensure_linux_ollama() -> dict:
    try:
        client = LinuxAgentClient()
        health = client.health()
        if health.get("status") != "ok":
            raise LinuxAgentError("Linux Agent de homologação não está pronto", status_code=503)
        return client.request("POST", "/v1/ollama/ensure", payload={})
    except LinuxAgentError as error:
        raise HTTPException(error.status_code, str(error)) from error


def _catalog_payload(runtime: dict, *, warning: str = "") -> dict:
    models = _normalize_models(runtime.get("models") or [])
    source = "live" if runtime.get("status") == "running" else "reference"
    if not models:
        models = list(REFERENCE_MODELS)
        if not warning:
            warning = (
                "A instância Ollama está ativa, mas ainda não há modelos instalados. "
                "Instale tinyllama ou outro modelo no Linux de homologação."
            )
    return {
        "provider": "ollama",
        "source": source,
        "models": [{"id": model, "label": model} for model in models],
        "recommended_models": [
            {"id": model, "label": model}
            for model in models
            if model in REFERENCE_MODELS
        ][:2] or [{"id": model, "label": model} for model in models[:2]],
        "runtime_status": runtime.get("status", "unknown"),
        "started": bool(runtime.get("started")),
        "warning": warning,
        "refreshed_at": datetime.now(timezone.utc),
    }


@router.get("/catalog")
def ollama_catalog():
    try:
        runtime = _ensure_linux_ollama()
        return _catalog_payload(runtime)
    except HTTPException as error:
        return _catalog_payload(
            {"status": "reference", "models": []},
            warning=str(error.detail),
        )


@router.post("/discover")
def discover_ollama(
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = _workspace(db)
    runtime = _ensure_linux_ollama()
    payload = _catalog_payload(runtime)
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="provider.ollama_discovered",
        details={
            "runtime_status": payload["runtime_status"],
            "started": payload["started"],
            "model_count": len(payload["models"]),
        },
    )
    db.commit()
    return payload


@router.post("/connect", status_code=201)
def connect_ollama(
    payload: OllamaConnectRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = _workspace(db)
    runtime = _ensure_linux_ollama()
    available = _normalize_models(runtime.get("models") or [])
    if not available:
        raise HTTPException(
            422,
            "Ollama foi iniciado no Linux de homologação, mas não há modelo instalado. "
            "Instale tinyllama ou outro modelo e tente novamente.",
        )

    selected = _normalize_models(payload.models) or [
        model for model in REFERENCE_MODELS if model in available
    ][:2] or available[:2]
    unavailable = sorted(set(selected) - set(available))
    if unavailable:
        raise HTTPException(
            422,
            f"Modelos não instalados no Ollama de homologação: {', '.join(unavailable[:5])}",
        )

    label = payload.label.strip()
    item = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == ws.id,
            ProviderCredential.provider == "ollama",
            ProviderCredential.label == label,
        )
    )
    created = item is None
    if item is None:
        item = ProviderCredential(
            workspace_id=ws.id,
            provider="ollama",
            label=label,
            encrypted_secret=Vault().encrypt("linux-agent-managed"),
            models="[]",
            enabled=True,
        )
        db.add(item)
        db.flush()

    item.models = json.dumps(selected)
    item.enabled = True
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="provider.ollama_connected" if created else "provider.ollama_reconnected",
        details={
            "connection_id": item.id,
            "label": item.label,
            "model_count": len(selected),
            "runtime_started": bool(runtime.get("started")),
        },
    )
    db.commit()
    return {
        "id": item.id,
        "provider": item.provider,
        "label": item.label,
        "models": selected,
        "enabled": item.enabled,
        "runtime_status": runtime.get("status", "unknown"),
        "runtime_started": bool(runtime.get("started")),
        "created_at": item.created_at,
    }
