from __future__ import annotations

import base64
import json
import os
from urllib.parse import quote

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
OPENAI_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
GOOGLE_INLINE_AUDIO_MAX_BYTES = 13 * 1024 * 1024
GOOGLE_FALLBACK_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
)
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


class ProviderTranscriptionError(RuntimeError):
    def __init__(self, provider: str, status_code: int, message: str):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.message = message


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if item:
        return item
    item = Workspace(name="DevPilot", slug="default")
    db.add(item)
    db.flush()
    return item


def _provider_credentials(
    db: Session,
    workspace_id: str,
    provider: str,
) -> list[ProviderCredential]:
    return list(
        db.scalars(
            select(ProviderCredential)
            .where(
                ProviderCredential.workspace_id == workspace_id,
                ProviderCredential.provider == provider,
                ProviderCredential.enabled.is_(True),
            )
            .order_by(ProviderCredential.created_at.desc())
        ).all()
    )


def _decrypt_secret(item: ProviderCredential) -> str:
    try:
        return Vault().decrypt(item.encrypted_secret).strip()
    except Exception:
        return ""


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _openai_api_keys(db: Session, workspace_id: str) -> list[str]:
    keys = [os.getenv("OPENAI_API_KEY", "").strip()]
    keys.extend(_decrypt_secret(item) for item in _provider_credentials(db, workspace_id, "openai"))
    return _dedupe(keys)


def _google_api_keys(db: Session, workspace_id: str) -> list[str]:
    keys = [
        os.getenv("GEMINI_API_KEY", "").strip(),
        os.getenv("GOOGLE_API_KEY", "").strip(),
    ]
    keys.extend(_decrypt_secret(item) for item in _provider_credentials(db, workspace_id, "google"))
    return _dedupe(keys)


def _stored_models(item: ProviderCredential) -> list[str]:
    try:
        values = json.loads(item.models or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _google_model_score(model: str) -> tuple[int, str]:
    value = model.lower()
    score = 0
    if "flash" in value:
        score += 100
    if "lite" in value:
        score += 15
    if "3.6" in value:
        score += 35
    elif "3.5" in value:
        score += 30
    elif "2.5" in value:
        score += 25
    if "preview" in value:
        score -= 10
    if any(token in value for token in ("live", "embedding", "image", "tts")):
        score -= 1000
    return score, value


def _google_model_candidates(db: Session, workspace_id: str) -> list[str]:
    models: list[str] = []
    for item in _provider_credentials(db, workspace_id, "google"):
        models.extend(_stored_models(item))
    models.extend(GOOGLE_FALLBACK_MODELS)
    candidates = [
        value.removeprefix("models/")
        for value in _dedupe(models)
        if value.lower().startswith(("gemini-", "models/gemini-"))
        and not any(token in value.lower() for token in ("live", "embedding", "image", "tts"))
    ]
    return sorted(candidates, key=_google_model_score, reverse=True)[:6]


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


def _provider_error(provider: str, statuses: list[int]) -> ProviderTranscriptionError:
    if 429 in statuses:
        return ProviderTranscriptionError(
            provider,
            429,
            f"Limite de transcrição do provedor {provider} atingido.",
        )
    if statuses and all(status in {401, 403} for status in statuses):
        return ProviderTranscriptionError(
            provider,
            503,
            f"A credencial de transcrição do provedor {provider} não está válida.",
        )
    if 400 in statuses or 415 in statuses or 422 in statuses:
        return ProviderTranscriptionError(
            provider,
            422,
            f"O provedor {provider} não conseguiu processar este áudio.",
        )
    return ProviderTranscriptionError(
        provider,
        502,
        f"O serviço de transcrição do provedor {provider} está temporariamente indisponível.",
    )


async def _transcribe_openai(
    client: httpx.AsyncClient,
    *,
    payload: bytes,
    filename: str,
    content_type: str,
    api_keys: list[str],
) -> tuple[str, str]:
    if not api_keys:
        raise ProviderTranscriptionError(
            "openai",
            503,
            "Nenhuma credencial OpenAI ativa está disponível para transcrição.",
        )

    statuses: list[int] = []
    files = {"file": (filename, payload, content_type)}
    data = {"model": OPENAI_TRANSCRIPTION_MODEL, "language": "pt"}

    for api_key in api_keys:
        try:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files=files,
            )
        except httpx.HTTPError:
            statuses.append(502)
            continue

        if response.status_code >= 400:
            statuses.append(response.status_code)
            continue

        try:
            text = str(response.json().get("text", "")).strip()
        except (ValueError, AttributeError):
            statuses.append(502)
            continue
        if text:
            return text, OPENAI_TRANSCRIPTION_MODEL
        statuses.append(422)

    raise _provider_error("openai", statuses)


def _google_response_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
        candidates = payload.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    except (ValueError, AttributeError, IndexError):
        return ""
    return " ".join(
        str(part.get("text", "")).strip()
        for part in parts
        if isinstance(part, dict) and str(part.get("text", "")).strip()
    ).strip()


async def _transcribe_google(
    client: httpx.AsyncClient,
    *,
    payload: bytes,
    content_type: str,
    api_keys: list[str],
    models: list[str],
) -> tuple[str, str]:
    if not api_keys:
        raise ProviderTranscriptionError(
            "google",
            503,
            "Nenhuma credencial Google ativa está disponível para fallback de transcrição.",
        )
    if not models:
        raise ProviderTranscriptionError(
            "google",
            503,
            "Nenhum modelo Google compatível está disponível para fallback de transcrição.",
        )

    audio_base64 = base64.b64encode(payload).decode("ascii")
    request_payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Transcreva este áudio em português do Brasil. "
                            "Retorne somente a fala transcrita, sem comentários, "
                            "sem Markdown e sem explicar a tarefa."
                        )
                    },
                    {
                        "inlineData": {
                            "mimeType": content_type,
                            "data": audio_base64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"temperature": 0},
    }
    statuses: list[int] = []

    for api_key in api_keys:
        for model in models:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{quote(model, safe='')}:generateContent"
            )
            try:
                response = await client.post(
                    url,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "x-goog-api-key": api_key,
                    },
                    json=request_payload,
                )
            except httpx.HTTPError:
                statuses.append(502)
                continue

            if response.status_code >= 400:
                statuses.append(response.status_code)
                continue

            text = _google_response_text(response)
            if text:
                return text, model
            statuses.append(422)

    raise _provider_error("google", statuses)


def _final_failure(
    primary: ProviderTranscriptionError,
    fallback: ProviderTranscriptionError | None,
) -> HTTPException:
    if fallback is None:
        if primary.status_code == 429:
            return HTTPException(
                429,
                "Limite de transcrição atingido. Digite o comando abaixo ou "
                "configure um provedor Google para fallback automático.",
            )
        return HTTPException(primary.status_code, primary.message)

    if primary.status_code == 429:
        return HTTPException(
            429,
            "Limite da OpenAI atingido e o fallback Google não conseguiu concluir a "
            "transcrição. Digite o comando abaixo ou revise as credenciais dos provedores.",
        )
    return HTTPException(
        fallback.status_code,
        "Os provedores de transcrição configurados não conseguiram processar o áudio. "
        "Digite o comando abaixo ou revise Modelos de IA.",
    )


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

    openai_keys = _openai_api_keys(db, ws.id)
    google_keys = _google_api_keys(db, ws.id)
    google_models = _google_model_candidates(db, ws.id) if google_keys else []

    provider = ""
    model = ""
    text = ""
    primary_error: ProviderTranscriptionError | None = None
    fallback_error: ProviderTranscriptionError | None = None

    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
        try:
            text, model = await _transcribe_openai(
                client,
                payload=payload,
                filename=_filename(audio.filename, content_type),
                content_type=content_type,
                api_keys=openai_keys,
            )
            provider = "openai"
        except ProviderTranscriptionError as error:
            primary_error = error

        if not text and google_keys and len(payload) <= GOOGLE_INLINE_AUDIO_MAX_BYTES:
            try:
                text, model = await _transcribe_google(
                    client,
                    payload=payload,
                    content_type=content_type,
                    api_keys=google_keys,
                    models=google_models,
                )
                provider = "google"
            except ProviderTranscriptionError as error:
                fallback_error = error

    if not text:
        record(
            db,
            workspace_id=ws.id,
            actor=actor,
            action="voice.transcription_failed",
            outcome="failed",
            details={
                "openai_status": primary_error.status_code if primary_error else None,
                "google_attempted": bool(google_keys) and len(payload) <= GOOGLE_INLINE_AUDIO_MAX_BYTES,
                "google_status": fallback_error.status_code if fallback_error else None,
                "bytes": len(payload),
                "content_type": content_type,
            },
        )
        db.commit()
        raise _final_failure(
            primary_error
            or ProviderTranscriptionError("openai", 502, "Falha de transcrição."),
            fallback_error,
        )

    record(
        db,
        workspace_id=ws.id,
        actor=actor,
        action="voice.transcribed",
        details={
            "provider": provider,
            "model": model,
            "fallback": provider != "openai",
            "bytes": len(payload),
            "content_type": content_type,
        },
    )
    db.commit()
    return {
        "text": text,
        "provider": provider,
        "model": model,
        "fallback": provider != "openai",
    }
