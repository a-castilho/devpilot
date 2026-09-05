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
from app.models import ProviderCredential
from app.security import require_access
from app.services.audit import record
from app.services.token_usage import (
    record_usage,
    serialize_usage,
    token_counts_from_usage,
    user_id_from_actor,
)
from app.services.vault import Vault
from app.services.workspace_scope import workspace_for_authenticated_session


router = APIRouter(prefix="/api")

MAX_AUDIO_BYTES = 15 * 1024 * 1024
GOOGLE_INLINE_AUDIO_MAX_BYTES = 13 * 1024 * 1024
OPENAI_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
GROQ_TRANSCRIPTION_MODELS = ("whisper-large-v3-turbo", "whisper-large-v3")
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


def _workspace(db: Session):
    return workspace_for_authenticated_session(db)


def _provider_credentials(db: Session, workspace_id: str, provider: str) -> list[ProviderCredential]:
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
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _stored_models(item: ProviderCredential) -> list[str]:
    try:
        values = json.loads(item.models or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _openai_api_keys(db: Session, workspace_id: str) -> list[str]:
    keys = [os.getenv("OPENAI_API_KEY", "").strip()]
    keys.extend(_decrypt_secret(item) for item in _provider_credentials(db, workspace_id, "openai"))
    return _dedupe(keys)


def _google_api_keys(db: Session, workspace_id: str) -> list[str]:
    keys = [os.getenv("GEMINI_API_KEY", "").strip(), os.getenv("GOOGLE_API_KEY", "").strip()]
    keys.extend(_decrypt_secret(item) for item in _provider_credentials(db, workspace_id, "google"))
    return _dedupe(keys)


def _is_groq_connection(item: ProviderCredential) -> bool:
    identity = f"{item.provider} {getattr(item, 'label', '')}".lower()
    models = " ".join(_stored_models(item)).lower()
    return "groq" in identity or (item.provider == "custom" and "whisper" in models)


def _groq_candidates(db: Session, workspace_id: str) -> list[tuple[str, list[str], str]]:
    candidates: list[tuple[str, list[str], str]] = []
    env_key = os.getenv("GROQ_API_KEY", "").strip()
    if env_key:
        env_models = [
            value.strip()
            for value in os.getenv("DEVPILOT_VOICE_GROQ_TRANSCRIPTION_MODELS", "").split(",")
            if value.strip()
        ]
        candidates.append((env_key, _dedupe([*env_models, *GROQ_TRANSCRIPTION_MODELS]), "env"))

    for provider in ("groq", "custom"):
        for item in _provider_credentials(db, workspace_id, provider):
            if not _is_groq_connection(item):
                continue
            secret = _decrypt_secret(item)
            if not secret:
                continue
            configured = [model for model in _stored_models(item) if "whisper" in model.lower()]
            models = _dedupe([*configured, *GROQ_TRANSCRIPTION_MODELS])
            candidates.append((secret, models, str(getattr(item, "id", ""))))
    return candidates


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
        "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a",
        "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav",
        "audio/aac": "aac", "audio/3gpp": "3gp", "audio/3gpp2": "3g2",
    }
    return f"voice.{extensions.get(content_type, 'webm')}"


def _provider_error(provider: str, statuses: list[int]) -> ProviderTranscriptionError:
    if 429 in statuses:
        return ProviderTranscriptionError(provider, 429, f"Limite de transcrição do provedor {provider} atingido.")
    if statuses and all(status in {401, 403} for status in statuses):
        return ProviderTranscriptionError(provider, 503, f"A credencial de transcrição do provedor {provider} não está válida.")
    if any(status in {400, 415, 422} for status in statuses):
        return ProviderTranscriptionError(provider, 422, f"O provedor {provider} não conseguiu processar este áudio.")
    return ProviderTranscriptionError(provider, 502, f"O serviço de transcrição do provedor {provider} está temporariamente indisponível.")


async def _transcribe_openai_compatible(
    client: httpx.AsyncClient,
    *,
    provider: str,
    endpoint: str,
    payload: bytes,
    filename: str,
    content_type: str,
    api_key: str,
    models: list[str],
) -> tuple[str, str, dict]:
    statuses: list[int] = []
    files = {"file": (filename, payload, content_type)}
    for model in models:
        try:
            response = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": model, "language": "pt"},
                files=files,
            )
        except httpx.HTTPError:
            statuses.append(502)
            continue
        if response.status_code >= 400:
            statuses.append(response.status_code)
            continue
        try:
            data = response.json()
        except ValueError:
            statuses.append(502)
            continue
        text = str(data.get("text", "")).strip() if isinstance(data, dict) else ""
        if text:
            raw_usage = data.get("usage") if isinstance(data, dict) else None
            return text, model, raw_usage if isinstance(raw_usage, dict) else {}
        statuses.append(422)
    raise _provider_error(provider, statuses)


async def _transcribe_groq(
    client: httpx.AsyncClient,
    *,
    payload: bytes,
    filename: str,
    content_type: str,
    candidates: list[tuple[str, list[str], str]],
) -> tuple[str, str, dict]:
    if not candidates:
        raise ProviderTranscriptionError("groq", 503, "Nenhuma conexão Groq/Whisper ativa está disponível para transcrição.")
    statuses: list[int] = []
    for api_key, models, _connection_id in candidates:
        try:
            return await _transcribe_openai_compatible(
                client,
                provider="groq",
                endpoint="https://api.groq.com/openai/v1/audio/transcriptions",
                payload=payload,
                filename=filename,
                content_type=content_type,
                api_key=api_key,
                models=models,
            )
        except ProviderTranscriptionError as error:
            statuses.append(error.status_code)
    raise _provider_error("groq", statuses)


async def _transcribe_openai(
    client: httpx.AsyncClient,
    *,
    payload: bytes,
    filename: str,
    content_type: str,
    api_keys: list[str],
) -> tuple[str, str, dict]:
    if not api_keys:
        raise ProviderTranscriptionError("openai", 503, "Nenhuma credencial OpenAI ativa está disponível para transcrição.")
    statuses: list[int] = []
    for api_key in api_keys:
        try:
            return await _transcribe_openai_compatible(
                client,
                provider="openai",
                endpoint="https://api.openai.com/v1/audio/transcriptions",
                payload=payload,
                filename=filename,
                content_type=content_type,
                api_key=api_key,
                models=[OPENAI_TRANSCRIPTION_MODEL],
            )
        except ProviderTranscriptionError as error:
            statuses.append(error.status_code)
    raise _provider_error("openai", statuses)


def _google_response_data(response: httpx.Response) -> tuple[str, dict]:
    try:
        payload = response.json()
    except ValueError:
        return "", {}
    if not isinstance(payload, dict):
        return "", {}
    collected: list[str] = []
    for candidate in payload.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        for part in content.get("parts") or [] if isinstance(content, dict) else []:
            if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
                collected.append(part["text"].strip())
    text = " ".join(collected).strip()
    if not text:
        for key in ("text", "output_text", "response"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                text = value.strip()
                break
    usage = payload.get("usageMetadata")
    return text, usage if isinstance(usage, dict) else {}


async def _transcribe_google(
    client: httpx.AsyncClient,
    *,
    payload: bytes,
    content_type: str,
    api_keys: list[str],
    models: list[str],
) -> tuple[str, str, dict]:
    if not api_keys or not models:
        raise ProviderTranscriptionError("google", 503, "Nenhuma configuração Google compatível está disponível para transcrição.")
    audio_base64 = base64.b64encode(payload).decode("ascii")
    request_payload = {
        "contents": [{"parts": [
            {"text": "Transcreva este áudio em português do Brasil. Retorne somente a fala transcrita, sem comentários e sem Markdown."},
            {"inlineData": {"mimeType": content_type, "data": audio_base64}},
        ]}],
        "generationConfig": {"temperature": 0},
    }
    statuses: list[int] = []
    for api_key in api_keys:
        for model in models:
            url = "https://generativelanguage.googleapis.com/v1beta/models/" + quote(model, safe="") + ":generateContent"
            try:
                response = await client.post(url, headers={"Accept": "application/json", "Content-Type": "application/json", "x-goog-api-key": api_key}, json=request_payload)
            except httpx.HTTPError:
                statuses.append(502)
                continue
            if response.status_code >= 400:
                statuses.append(response.status_code)
                continue
            text, usage = _google_response_data(response)
            if text:
                return text, model, usage
            statuses.append(422)
    raise _provider_error("google", statuses)


def _provider_order(has_groq: bool, has_openai: bool, has_google: bool) -> list[str]:
    configured = [value.strip().lower() for value in os.getenv("DEVPILOT_VOICE_TRANSCRIPTION_PROVIDER_ORDER", "").split(",") if value.strip()]
    supported = {"groq", "openai", "google"}
    available = {"groq": has_groq, "openai": has_openai, "google": has_google}
    order = [value for value in configured if value in supported and available.get(value)]
    for provider in ("groq", "openai", "google"):
        if available[provider] and provider not in order:
            order.append(provider)
    return order


def _final_failure(errors: list[ProviderTranscriptionError]) -> HTTPException:
    if not errors:
        return HTTPException(503, "Nenhum provedor de transcrição está configurado. Revise Modelos de IA.")
    status = 429 if any(error.status_code == 429 for error in errors) else errors[-1].status_code
    attempted = ", ".join(error.provider for error in errors)
    return HTTPException(status, f"Os provedores de transcrição ({attempted}) não conseguiram processar o áudio. Revise Modelos de IA ou tente novamente.")


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

    filename = _filename(audio.filename, content_type)
    groq_candidates = _groq_candidates(db, ws.id)
    openai_keys = _openai_api_keys(db, ws.id)
    google_keys = _google_api_keys(db, ws.id)
    google_models = _google_model_candidates(db, ws.id) if google_keys else []
    order = _provider_order(bool(groq_candidates), bool(openai_keys), bool(google_keys and len(payload) <= GOOGLE_INLINE_AUDIO_MAX_BYTES))

    provider = ""
    model = ""
    text = ""
    usage_payload: dict = {}
    errors: list[ProviderTranscriptionError] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
        for candidate in order:
            try:
                if candidate == "groq":
                    text, model, usage_payload = await _transcribe_groq(client, payload=payload, filename=filename, content_type=content_type, candidates=groq_candidates)
                elif candidate == "openai":
                    text, model, usage_payload = await _transcribe_openai(client, payload=payload, filename=filename, content_type=content_type, api_keys=openai_keys)
                else:
                    text, model, usage_payload = await _transcribe_google(client, payload=payload, content_type=content_type, api_keys=google_keys, models=google_models)
                if text:
                    provider = candidate
                    break
            except ProviderTranscriptionError as error:
                errors.append(error)

    if not text:
        record(db, workspace_id=ws.id, actor=actor, action="voice.transcription_failed", outcome="failed", details={
            "attempts": [{"provider": error.provider, "status": error.status_code} for error in errors],
            "provider_order": order,
            "bytes": len(payload),
            "content_type": content_type,
        })
        db.commit()
        raise _final_failure(errors)

    usage = record_usage(
        db,
        workspace_id=ws.id,
        user_id=user_id_from_actor(actor),
        provider=provider,
        model=model,
        operation="voice.transcription",
        counts=token_counts_from_usage(usage_payload),
    )
    record(db, workspace_id=ws.id, actor=actor, action="voice.transcribed", details={
        "provider": provider,
        "model": model,
        "fallback": bool(order) and provider != order[0],
        "provider_order": order,
        "attempts": [{"provider": error.provider, "status": error.status_code} for error in errors],
        "bytes": len(payload),
        "content_type": content_type,
    })
    db.commit()

    result = {
        "text": text,
        "provider": provider,
        "model": model,
        "fallback": bool(order) and provider != order[0],
        "provider_order": order,
    }
    if usage:
        result["token_usage"] = serialize_usage(usage)
    return result
