from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditEvent, ProviderCredential, TokenUsage, Workspace
from app.security import require_super_admin


router = APIRouter(
    prefix="/api/super-admin/voice",
    tags=["super-admin-voice"],
    dependencies=[Depends(require_super_admin)],
)


def _workspace(db: Session) -> Workspace | None:
    return db.scalar(select(Workspace).where(Workspace.slug == "default"))


def _models(item: ProviderCredential) -> list[str]:
    try:
        raw = json.loads(item.models or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [str(value).strip() for value in raw if str(value).strip()]


def _details(event: AuditEvent | None) -> dict:
    if not event:
        return {}
    try:
        value = json.loads(event.details or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _has_env(*names: str) -> bool:
    return any(bool(os.getenv(name, "").strip()) for name in names)


@router.get("")
def voice_admin_dashboard(db: Session = Depends(get_db)):
    """Return a secret-free operational view of the DevPilVoz transcription chain."""
    ws = _workspace(db)
    now = datetime.now(timezone.utc)
    if not ws:
        return {
            "generated_at": now,
            "chain": [],
            "connections": [],
            "last_transcription": None,
            "recent_events": [],
            "usage_24h": [],
            "warnings": ["Workspace padrão ainda não foi criado."],
        }

    credentials = list(
        db.scalars(
            select(ProviderCredential)
            .where(ProviderCredential.workspace_id == ws.id)
            .order_by(ProviderCredential.created_at.desc())
        ).all()
    )
    enabled = [item for item in credentials if item.enabled]
    active_by_provider: dict[str, list[ProviderCredential]] = {}
    for item in enabled:
        active_by_provider.setdefault(item.provider.lower(), []).append(item)

    openai_ready = _has_env("OPENAI_API_KEY") or bool(active_by_provider.get("openai"))
    google_ready = _has_env("GEMINI_API_KEY", "GOOGLE_API_KEY") or bool(active_by_provider.get("google"))

    chain = [
        {
            "order": 1,
            "provider": "openai",
            "label": "OpenAI",
            "role": "principal",
            "model": "gpt-4o-mini-transcribe",
            "configured": openai_ready,
        },
        {
            "order": 2,
            "provider": "google",
            "label": "Gemini / Google",
            "role": "fallback",
            "model": "catálogo Gemini Flash selecionado automaticamente",
            "configured": google_ready,
        },
    ]

    connections = [
        {
            "id": item.id,
            "provider": item.provider,
            "label": item.label,
            "enabled": item.enabled,
            "models": _models(item),
            "created_at": item.created_at,
            "used_by_voice_transcription": item.provider.lower() in {"openai", "google"},
        }
        for item in credentials
    ]

    event_query = (
        select(AuditEvent)
        .where(
            AuditEvent.workspace_id == ws.id,
            AuditEvent.action.in_(("voice.transcribed", "voice.transcription_failed")),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(30)
    )
    events = list(db.scalars(event_query).all())
    latest_success = next((event for event in events if event.action == "voice.transcribed"), None)
    latest_details = _details(latest_success)

    recent_events = []
    for event in events[:12]:
        detail = _details(event)
        recent_events.append(
            {
                "id": event.id,
                "action": event.action,
                "outcome": event.outcome,
                "created_at": event.created_at,
                "provider": detail.get("provider"),
                "model": detail.get("model"),
                "fallback": bool(detail.get("fallback", False)),
                "openai_status": detail.get("openai_status"),
                "google_status": detail.get("google_status"),
            }
        )

    since = now - timedelta(hours=24)
    usage_rows = db.execute(
        select(
            TokenUsage.provider,
            TokenUsage.model,
            func.count(TokenUsage.id),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
        )
        .where(
            TokenUsage.workspace_id == ws.id,
            TokenUsage.operation == "voice.transcription",
            TokenUsage.created_at >= since,
        )
        .group_by(TokenUsage.provider, TokenUsage.model)
        .order_by(func.count(TokenUsage.id).desc())
    ).all()
    usage_24h = [
        {
            "provider": provider,
            "model": model,
            "requests": int(requests or 0),
            "tokens": int(tokens or 0),
        }
        for provider, model, requests, tokens in usage_rows
    ]

    warnings: list[str] = []
    voice_inactive = [
        item for item in enabled
        if item.provider.lower() not in {"openai", "google"}
        and any("whisper" in model.lower() for model in _models(item))
    ]
    if voice_inactive:
        labels = ", ".join(item.label for item in voice_inactive[:4])
        warnings.append(
            f"{labels}: conexão com modelo Whisper está cadastrada, mas a cadeia atual de transcrição usa somente OpenAI → Google."
        )
    if not openai_ready:
        warnings.append("OpenAI principal não possui credencial ativa para transcrição.")
    if not google_ready:
        warnings.append("Google/Gemini fallback não possui credencial ativa.")

    return {
        "generated_at": now,
        "chain": chain,
        "connections": connections,
        "last_transcription": (
            {
                "created_at": latest_success.created_at,
                "provider": latest_details.get("provider"),
                "model": latest_details.get("model"),
                "fallback": bool(latest_details.get("fallback", False)),
            }
            if latest_success
            else None
        ),
        "recent_events": recent_events,
        "usage_24h": usage_24h,
        "warnings": warnings,
    }
