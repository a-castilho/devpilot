from __future__ import annotations

import asyncio
import os
import shutil
import subprocess

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential, Workspace
from app.security import require_access
from app.services.audit import record
from app.services.vault import Vault


router = APIRouter(prefix="/api")

OPENAI_TTS_MODEL = "gpt-4o-mini-tts"
OPENAI_TTS_VOICES = {
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "onyx",
    "nova",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
}
LOCAL_TTS_VOICES = {
    "human": ("pt-br", 165, 50),
    "male": ("pt-br+m3", 158, 42),
    "female": ("pt-br+f3", 172, 58),
    "machine": ("pt-br+m1", 145, 30),
}


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    voice: str = Field(default="coral", max_length=32)


class LocalSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4096)
    voice: str = Field(default="human", max_length=32)


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if item:
        return item
    item = Workspace(name="DevPilot", slug="default")
    db.add(item)
    db.flush()
    return item


def _decrypt_secret(item: ProviderCredential) -> str:
    try:
        return Vault().decrypt(item.encrypted_secret).strip()
    except Exception:
        return ""


def _openai_api_keys(db: Session, workspace_id: str) -> list[str]:
    values = [os.getenv("OPENAI_API_KEY", "").strip()]
    credentials = db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == "openai",
            ProviderCredential.enabled.is_(True),
        )
        .order_by(ProviderCredential.created_at.desc())
    ).all()
    values.extend(_decrypt_secret(item) for item in credentials)

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _failure(statuses: list[int]) -> HTTPException:
    if 429 in statuses:
        return HTTPException(
            429,
            "Limite de voz da OpenAI atingido. Escolha uma voz local ou tente novamente depois.",
        )
    if statuses and all(status in {401, 403} for status in statuses):
        return HTTPException(
            503,
            "A credencial OpenAI não está válida para voz. Revise Modelos de IA.",
        )
    return HTTPException(
        502,
        "A voz ChatGPT está temporariamente indisponível. Escolha uma voz local.",
    )


def _render_local_speech(text: str, mode: str) -> bytes:
    executable = shutil.which("espeak-ng")
    if not executable:
        raise RuntimeError("Motor local espeak-ng não está instalado.")

    voice, speed, pitch = LOCAL_TTS_VOICES[mode]
    command = [
        executable,
        "--stdout",
        "--stdin",
        "-v",
        voice,
        "-s",
        str(speed),
        "-p",
        str(pitch),
        "-a",
        "180",
    ]
    try:
        result = subprocess.run(
            command,
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("O motor de voz local não conseguiu iniciar.") from exc

    if result.returncode != 0 or len(result.stdout) <= 44:
        detail = result.stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(detail or "O motor de voz local não gerou áudio.")

    return result.stdout


@router.post("/voice/speech/local")
async def create_local_speech(
    payload: LocalSpeechRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = _workspace(db)
    text = payload.text.strip()
    if not text:
        raise HTTPException(422, "Informe uma transcrição para ouvir.")

    mode = payload.voice.strip().lower()
    if mode not in LOCAL_TTS_VOICES:
        raise HTTPException(422, "Voz local não suportada.")

    try:
        audio = await asyncio.to_thread(_render_local_speech, text, mode)
    except RuntimeError as exc:
        record(
            db,
            workspace_id=ws.id,
            actor=actor,
            action="voice.local_speech_failed",
            outcome="failed",
            details={"engine": "espeak-ng", "voice": mode, "characters": len(text)},
        )
        db.commit()
        raise HTTPException(
            503,
            "A voz local do servidor está indisponível. Atualize o container do DevPilot.",
        ) from exc

    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="voice.local_speech_generated",
        details={
            "provider": "local",
            "engine": "espeak-ng",
            "voice": mode,
            "characters": len(text),
        },
    )
    db.commit()
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.post("/voice/speech")
async def create_speech(
    payload: SpeechRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = _workspace(db)
    text = payload.text.strip()
    if not text:
        raise HTTPException(422, "Informe uma transcrição para ouvir.")

    voice = payload.voice.strip().lower()
    if voice not in OPENAI_TTS_VOICES:
        raise HTTPException(422, "Voz ChatGPT não suportada.")

    api_keys = _openai_api_keys(db, ws.id)
    if not api_keys:
        raise HTTPException(
            503,
            "Nenhuma credencial OpenAI ativa está disponível para a voz ChatGPT.",
        )

    request_payload = {
        "model": OPENAI_TTS_MODEL,
        "input": text,
        "voice": voice,
        "response_format": "mp3",
        "instructions": (
            "Fale em português do Brasil com voz natural, clara e calma. "
            "Leia exatamente o texto recebido, sem adicionar comentários."
        ),
    }
    statuses: list[int] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
        for api_key in api_keys:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                )
            except httpx.HTTPError:
                statuses.append(502)
                continue

            if response.status_code >= 400:
                statuses.append(response.status_code)
                continue

            if not response.content:
                statuses.append(502)
                continue

            record(
                db,
                workspace_id=ws.id,
                actor=actor,
                action="voice.speech_generated",
                details={
                    "provider": "openai",
                    "model": OPENAI_TTS_MODEL,
                    "voice": voice,
                    "characters": len(text),
                },
            )
            db.commit()
            return Response(
                content=response.content,
                media_type="audio/mpeg",
                headers={"Cache-Control": "no-store, max-age=0"},
            )

    error = _failure(statuses)
    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="voice.speech_failed",
        outcome="failed",
        details={
            "provider": "openai",
            "model": OPENAI_TTS_MODEL,
            "voice": voice,
            "characters": len(text),
            "statuses": statuses[-5:],
        },
    )
    db.commit()
    raise error
