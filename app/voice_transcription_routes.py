from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential, Workspace
from app.security import require_access
from app.services.audit import record
from app.services.vault import Vault


router = APIRouter(prefix="/api")

MAX_AUDIO_BYTES = 15 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/aac",
    "audio/3gpp",
    "audio/3gpp2",
}


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if item:
        return item
    item = Workspace(name="DevPilot", slug="default")
    db.add(item)
    db.flush()
    return item


def _openai_api_key(db: Session, workspace_id: str) -> str:
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key

    credential = db.scalar(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == "openai",
            ProviderCredential.enabled.is_(True),
        )
        .order_by(ProviderCredential.created_at.desc())
    )
    if not credential:
        raise HTTPException(
            503,
            "Transcrição compatível indisponível: conecte uma chave OpenAI em Modelos de IA.",
        )
    try:
        return Vault().decrypt(credential.encrypted_secret)
    except Exception as error:
        raise HTTPException(503, "Não foi possível abrir a credencial OpenAI configurada.") from error


def _filename(filename: str | None, content_type: str) -> str:
    if filename:
        return filename
    extensions = {
        "audio/webm": "webm",
        "audio/ogg": "ogg",
        "audio/mp4": "m4a",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/aac": "aac",
        "audio/3gpp": "3gp",
        "audio/3gpp2": "3g2",
    }
    return f"voice.{extensions.get(content_type, 'webm')}"


@router.post("/voice/transcriptions")
async def transcribe_voice(
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = _workspace(db)
    content_type = (audio.content_type or "audio/webm").split(";", 1)[0].lower()
    if content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(415, f"Formato de áudio não suportado: {content_type}")

    payload = await audio.read(MAX_AUDIO_BYTES + 1)
    if not payload:
        raise HTTPException(422, "Áudio vazio.")
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Áudio muito grande. Grave um comando mais curto.")

    api_key = _openai_api_key(db, ws.id)
    files = {
        "file": (
            _filename(audio.filename, content_type),
            payload,
            content_type,
        )
    }
    data = {
        "model": "gpt-4o-mini-transcribe",
        "language": "pt",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files=files,
            )
    except httpx.HTTPError as error:
        raise HTTPException(502, "Falha de rede ao transcrever o áudio.") from error

    if response.status_code >= 400:
        message = "O provedor de transcrição recusou o áudio."
        try:
            provider_message = str(response.json().get("error", {}).get("message", "")).strip()
            if provider_message:
                message = provider_message[:300]
        except (ValueError, AttributeError):
            pass
        raise HTTPException(502, message)

    try:
        text = str(response.json().get("text", "")).strip()
    except (ValueError, AttributeError) as error:
        raise HTTPException(502, "Resposta inválida do provedor de transcrição.") from error

    if not text:
        raise HTTPException(422, "Nenhuma fala foi reconhecida.")

    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="voice.transcribed",
        details={
            "provider": "openai",
            "model": data["model"],
            "bytes": len(payload),
            "content_type": content_type,
        },
    )
    db.commit()
    return {"text": text, "provider": "openai", "model": data["model"]}
