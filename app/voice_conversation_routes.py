from __future__ import annotations

import asyncio
import json
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, ProviderCredential
from app.security import require_access
from app.services.ai_costs import budget_block_reason
from app.services.audit import record
from app.services.token_usage import (
    record_usage,
    serialize_usage,
    token_counts_from_usage,
    user_id_from_actor,
)
from app.services.vault import Vault
from app.services.workspace_scope import workspace_for_authenticated_session


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])

DEFAULT_CHAT_MODELS = ("gpt-5.6", "gpt-5", "gpt-4.1-mini")
DEFAULT_GOOGLE_CHAT_MODELS = ("gemini-2.5-flash",)
DEFAULT_OLLAMA_CHAT_MODELS = ("phi3:mini", "tinyllama")
SUPPORTED_VOICE_PROVIDERS = ("openai", "google", "ollama")
MAX_HISTORY_ITEMS = 12
MAX_PROVIDER_ATTEMPTS_LOGGED = 24


class ConversationTurn(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    text: str = Field(min_length=1, max_length=4000)


class VoiceConversationRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)
    project_id: str | None = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)


def _workspace(db: Session):
    return workspace_for_authenticated_session(db)


def _decrypt_secret(item: ProviderCredential) -> str:
    try:
        return Vault().decrypt(item.encrypted_secret).strip()
    except Exception:
        return ""


def _provider_api_keys(db: Session, workspace_id: str, provider: str) -> list[str]:
    env_names = {
        "openai": ("OPENAI_API_KEY",),
        "google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    }
    values = [os.getenv(name, "").strip() for name in env_names.get(provider, ())]
    credentials = db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == provider,
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


def _openai_api_keys(db: Session, workspace_id: str) -> list[str]:
    return _provider_api_keys(db, workspace_id, "openai")


def _stored_provider_models(db: Session, workspace_id: str, provider: str) -> list[str]:
    credentials = db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == provider,
            ProviderCredential.enabled.is_(True),
        )
        .order_by(ProviderCredential.created_at.desc())
    ).all()
    result: list[str] = []
    for item in credentials:
        try:
            values = json.loads(item.models or "[]")
        except (TypeError, ValueError):
            continue
        if not isinstance(values, list):
            continue
        for value in values:
            model = str(value or "").strip()
            if model and model not in result:
                result.append(model)
    return result


def _split_env_list(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


def _chat_models() -> list[str]:
    configured = os.getenv("DEVPILOT_VOICE_CHAT_MODEL", "").strip()
    configured_many = _split_env_list("DEVPILOT_VOICE_OPENAI_MODELS")
    values = [configured, *configured_many, *DEFAULT_CHAT_MODELS]
    return list(dict.fromkeys(value for value in values if value))


def _google_chat_models(db: Session, workspace_id: str) -> list[str]:
    configured = _split_env_list("DEVPILOT_VOICE_GOOGLE_MODELS")
    stored = [
        model
        for model in _stored_provider_models(db, workspace_id, "google")
        if "gemini" in model.lower()
    ]
    values = [*configured, *stored, *DEFAULT_GOOGLE_CHAT_MODELS]
    return list(dict.fromkeys(value for value in values if value))


def _ollama_preferred_models() -> list[str]:
    configured = _split_env_list("DEVPILOT_VOICE_OLLAMA_MODELS")
    return list(dict.fromkeys([*configured, *DEFAULT_OLLAMA_CHAT_MODELS]))


def _ollama_base_urls() -> list[str]:
    configured = _split_env_list("DEVPILOT_OLLAMA_BASE_URLS")
    single = os.getenv("DEVPILOT_OLLAMA_BASE_URL", "").strip()
    values = [
        *configured,
        single,
        "http://host.docker.internal:11434",
        "http://127.0.0.1:11434",
        "http://172.17.0.1:11434",
    ]
    return list(dict.fromkeys(value.rstrip("/") for value in values if value))


def _provider_order() -> list[str]:
    configured = [value.lower() for value in _split_env_list("DEVPILOT_VOICE_PROVIDER_ORDER")]
    values = configured or list(SUPPORTED_VOICE_PROVIDERS)
    result = [value for value in values if value in SUPPORTED_VOICE_PROVIDERS]
    for provider in SUPPORTED_VOICE_PROVIDERS:
        if provider not in result:
            result.append(provider)
    return result


def _project_context(db: Session, workspace_id: str, project_id: str | None) -> str:
    if not project_id:
        return "Nenhum projeto foi selecionado. Converse em nível geral e peça contexto somente quando necessário."
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if not project:
        raise HTTPException(404, "Projeto não encontrado")
    description = (project.description or "").strip() or "Sem descrição cadastrada."
    return (
        f"Projeto selecionado: {project.name}. "
        f"Descrição: {description}. "
        f"Repositório: {project.repository_url}. "
        f"Branch padrão: {project.default_branch}."
    )


def _conversation_input(payload: VoiceConversationRequest, project_context: str) -> str:
    lines = [project_context, "", "Histórico recente da conversa:"]
    for turn in payload.history[-MAX_HISTORY_ITEMS:]:
        speaker = "CLIENTE" if turn.role == "user" else "DEVPILOT"
        lines.append(f"{speaker}: {turn.text.strip()}")
    lines.extend(["", f"CLIENTE: {payload.transcript.strip()}", "DEVPILOT:"])
    return "\n".join(lines)


def _instructions() -> str:
    return (
        "Você é o DevPilot, consultor de desenvolvimento que conversa diretamente com o cliente. "
        "Responda sempre em português do Brasil, de forma natural, objetiva e própria para ser falada em voz alta. "
        "Entenda a intenção antes de sugerir implementação. Faça no máximo uma pergunta quando faltar informação essencial. "
        "Quando o cliente pedir uma alteração, explique brevemente o que será feito e o próximo passo. "
        "Não invente que uma alteração foi executada se ela ainda não foi executada. "
        "Evite Markdown, listas longas, URLs e blocos de código na resposta falada. "
        "Mantenha a resposta normalmente entre uma e quatro frases."
    )


def _response_text(data: dict) -> str:
    direct = str(data.get("output_text") or "").strip()
    if direct:
        return direct
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text":
                text = str(content.get("text") or "").strip()
                if text:
                    return text
    return ""


def _google_response_text(data: dict) -> str:
    for candidate in data.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            continue
        parts = content.get("parts") or []
        text = " ".join(
            str(part.get("text") or "").strip()
            for part in parts
            if isinstance(part, dict) and str(part.get("text") or "").strip()
        ).strip()
        if text:
            return text
    return ""


def _ollama_response_text(data: dict) -> str:
    message = data.get("message") or {}
    if isinstance(message, dict):
        text = str(message.get("content") or "").strip()
        if text:
            return text
    return str(data.get("response") or "").strip()


def _provider_error_metadata(response: httpx.Response) -> dict:
    error_type = ""
    error_code = ""
    message = ""
    try:
        data = response.json()
    except ValueError:
        data = {}
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            error_type = str(error.get("type") or error.get("status") or "")[:120]
            error_code = str(error.get("code") or error.get("status") or "")[:120]
            message = str(error.get("message") or "")[:500]
        elif error:
            message = str(error)[:500]
    return {
        "status": int(response.status_code),
        "error_type": error_type,
        "error_code": error_code,
        "message": message,
        "request_id": str(response.headers.get("x-request-id") or "")[:200],
    }


def _quota_exhausted(metadata: dict) -> bool:
    value = " ".join(
        str(metadata.get(key) or "").lower()
        for key in ("error_type", "error_code", "message")
    )
    return any(
        fragment in value
        for fragment in (
            "insufficient_quota",
            "billing_hard_limit",
            "billing limit",
            "quota exceeded",
            "exceeded your current quota",
        )
    )


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    raw = str(response.headers.get("retry-after") or "").strip()
    try:
        return min(4.0, max(0.25, float(raw)))
    except ValueError:
        return min(2.0, 0.5 * (2**attempt))


def _attempt(provider: str, model: str, **details) -> dict:
    return {"provider": provider, "model": model, **details}


async def _try_openai(
    client: httpx.AsyncClient,
    db: Session,
    workspace_id: str,
    input_text: str,
    instructions: str,
) -> tuple[dict | None, list[dict]]:
    attempts: list[dict] = []
    keys = _openai_api_keys(db, workspace_id)
    if not keys:
        return None, [_attempt("openai", "", status=0, error_code="not_configured")]

    for api_key in keys:
        for model in _chat_models():
            for retry in range(2):
                try:
                    response = await client.post(
                        "https://api.openai.com/v1/responses",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "instructions": instructions,
                            "input": input_text,
                            "max_output_tokens": 280,
                            "store": False,
                        },
                    )
                except httpx.HTTPError as error:
                    attempts.append(
                        _attempt(
                            "openai",
                            model,
                            status=502,
                            error_type=type(error).__name__,
                            error_code="network_error",
                        )
                    )
                    break

                if response.status_code >= 400:
                    metadata = _provider_error_metadata(response)
                    attempts.append(_attempt("openai", model, **metadata))
                    if (
                        response.status_code == 429
                        and not _quota_exhausted(metadata)
                        and retry == 0
                    ):
                        await asyncio.sleep(_retry_delay(response, retry))
                        continue
                    break

                try:
                    data = response.json()
                except ValueError:
                    attempts.append(
                        _attempt("openai", model, status=502, error_code="invalid_json")
                    )
                    break

                answer = _response_text(data)
                if not answer:
                    attempts.append(
                        _attempt("openai", model, status=502, error_code="empty_response")
                    )
                    break
                raw_usage = data.get("usage")
                return {
                    "answer": answer,
                    "provider": "openai",
                    "model": model,
                    "usage": raw_usage if isinstance(raw_usage, dict) else {},
                }, attempts
    return None, attempts


async def _try_google(
    client: httpx.AsyncClient,
    db: Session,
    workspace_id: str,
    input_text: str,
    instructions: str,
) -> tuple[dict | None, list[dict]]:
    attempts: list[dict] = []
    keys = _provider_api_keys(db, workspace_id, "google")
    if not keys:
        return None, [_attempt("google", "", status=0, error_code="not_configured")]

    for api_key in keys:
        for model in _google_chat_models(db, workspace_id):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            for retry in range(2):
                try:
                    response = await client.post(
                        url,
                        params={"key": api_key},
                        headers={"Content-Type": "application/json"},
                        json={
                            "systemInstruction": {"parts": [{"text": instructions}]},
                            "contents": [{"role": "user", "parts": [{"text": input_text}]}],
                            "generationConfig": {"maxOutputTokens": 280},
                        },
                    )
                except httpx.HTTPError as error:
                    attempts.append(
                        _attempt(
                            "google",
                            model,
                            status=502,
                            error_type=type(error).__name__,
                            error_code="network_error",
                        )
                    )
                    break

                if response.status_code >= 400:
                    metadata = _provider_error_metadata(response)
                    attempts.append(_attempt("google", model, **metadata))
                    if response.status_code == 429 and retry == 0:
                        await asyncio.sleep(_retry_delay(response, retry))
                        continue
                    break

                try:
                    data = response.json()
                except ValueError:
                    attempts.append(
                        _attempt("google", model, status=502, error_code="invalid_json")
                    )
                    break

                answer = _google_response_text(data)
                if not answer:
                    attempts.append(
                        _attempt("google", model, status=502, error_code="empty_response")
                    )
                    break
                raw_usage = data.get("usageMetadata")
                return {
                    "answer": answer,
                    "provider": "google",
                    "model": model,
                    "usage": raw_usage if isinstance(raw_usage, dict) else {},
                }, attempts
    return None, attempts


async def _ollama_models(client: httpx.AsyncClient, base_url: str) -> list[str]:
    response = await client.get(f"{base_url}/api/tags", timeout=4.0)
    response.raise_for_status()
    data = response.json()
    discovered = []
    for item in data.get("models") or []:
        if not isinstance(item, dict):
            continue
        model = str(item.get("model") or item.get("name") or "").strip()
        if model and model not in discovered:
            discovered.append(model)
    preferred = _ollama_preferred_models()
    ordered = [model for model in preferred if model in discovered]
    ordered.extend(model for model in discovered if model not in ordered)
    return ordered[:5]


async def _try_ollama(
    client: httpx.AsyncClient,
    input_text: str,
    instructions: str,
) -> tuple[dict | None, list[dict]]:
    attempts: list[dict] = []
    for base_url in _ollama_base_urls():
        try:
            models = await _ollama_models(client, base_url)
        except (httpx.HTTPError, ValueError) as error:
            attempts.append(
                _attempt(
                    "ollama",
                    base_url,
                    status=502,
                    error_type=type(error).__name__,
                    error_code="unreachable",
                )
            )
            continue

        if not models:
            attempts.append(
                _attempt("ollama", base_url, status=503, error_code="no_local_models")
            )
            continue

        for model in models:
            try:
                response = await client.post(
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": instructions},
                            {"role": "user", "content": input_text},
                        ],
                        "options": {"num_predict": 280},
                    },
                    timeout=httpx.Timeout(60.0, connect=4.0),
                )
            except httpx.HTTPError as error:
                attempts.append(
                    _attempt(
                        "ollama",
                        model,
                        status=502,
                        error_type=type(error).__name__,
                        error_code="network_error",
                    )
                )
                continue

            if response.status_code >= 400:
                metadata = _provider_error_metadata(response)
                attempts.append(_attempt("ollama", model, **metadata))
                continue

            try:
                data = response.json()
            except ValueError:
                attempts.append(
                    _attempt("ollama", model, status=502, error_code="invalid_json")
                )
                continue

            answer = _ollama_response_text(data)
            if not answer:
                attempts.append(
                    _attempt("ollama", model, status=502, error_code="empty_response")
                )
                continue
            usage = {
                "input_tokens": data.get("prompt_eval_count") or 0,
                "output_tokens": data.get("eval_count") or 0,
                "total_tokens": (data.get("prompt_eval_count") or 0)
                + (data.get("eval_count") or 0),
            }
            return {
                "answer": answer,
                "provider": "ollama",
                "model": model,
                "usage": usage,
            }, attempts
    return None, attempts


def _provider_failure(attempts: list[dict]) -> HTTPException:
    external = [item for item in attempts if item.get("provider") in {"openai", "google"}]
    quota = any(_quota_exhausted(item) for item in external)
    statuses = [int(item.get("status") or 0) for item in attempts]
    if quota:
        return HTTPException(
            503,
            "A cota do provedor principal acabou e nenhum fallback configurado respondeu. Configure Gemini ou mantenha o Ollama local ativo.",
        )
    if 429 in statuses:
        return HTTPException(
            503,
            "Os provedores externos estão temporariamente limitados e o modo local não respondeu. Tente novamente em instantes.",
        )
    if attempts and all(int(item.get("status") or 0) == 0 for item in attempts):
        return HTTPException(
            503,
            "Nenhum provedor de conversa está configurado. Configure OpenAI ou Gemini, ou mantenha o Ollama local ativo.",
        )
    return HTTPException(
        502,
        "Nenhum provedor conseguiu responder. O DevPilot tentou os fallbacks configurados automaticamente.",
    )


def _fallback_notice(provider: str, primary: str) -> str:
    if provider == primary:
        return ""
    if provider == "google":
        return "Provedor principal indisponível; usando Google Gemini automaticamente."
    if provider == "ollama":
        return "Provedores externos indisponíveis; usando Ollama local automaticamente."
    return f"Usando {provider} como fallback automático."


@router.post("/voice/chat")
async def voice_chat(
    payload: VoiceConversationRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = _workspace(db)
    project_context = _project_context(db, ws.id, payload.project_id)
    user_id = user_id_from_actor(actor)
    budget_reason = budget_block_reason(
        db,
        workspace_id=ws.id,
        user_id=user_id,
        project_id=payload.project_id,
    )

    input_text = _conversation_input(payload, project_context)
    instructions = _instructions()
    provider_order = _provider_order()
    effective_order = list(provider_order)

    if budget_reason:
        record(
            db,
            workspace_id=ws.id,
            project_id=payload.project_id,
            actor=actor,
            action="ai.budget.blocked",
            outcome="blocked",
            details={
                "operation": "voice.chat.paid_providers",
                "reason": budget_reason,
                "fallback": "ollama",
            },
        )
        effective_order = [provider for provider in provider_order if provider == "ollama"]

    result: dict | None = None
    attempts: list[dict] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
        for provider in effective_order:
            if provider == "openai":
                candidate, provider_attempts = await _try_openai(
                    client, db, ws.id, input_text, instructions
                )
            elif provider == "google":
                candidate, provider_attempts = await _try_google(
                    client, db, ws.id, input_text, instructions
                )
            else:
                candidate, provider_attempts = await _try_ollama(
                    client, input_text, instructions
                )
            attempts.extend(provider_attempts)
            if candidate:
                result = candidate
                break

    if not result:
        if budget_reason:
            record(
                db,
                workspace_id=ws.id,
                project_id=payload.project_id,
                actor=actor,
                action="voice.chat_failed",
                outcome="blocked",
                details={
                    "reason": budget_reason,
                    "attempts": attempts[-MAX_PROVIDER_ATTEMPTS_LOGGED:],
                    "history_items": len(payload.history),
                },
            )
            db.commit()
            raise HTTPException(402, budget_reason)

        error = _provider_failure(attempts)
        record(
            db,
            workspace_id=ws.id,
            project_id=payload.project_id,
            actor=actor,
            action="voice.chat_failed",
            outcome="failed",
            details={
                "attempts": attempts[-MAX_PROVIDER_ATTEMPTS_LOGGED:],
                "history_items": len(payload.history),
            },
        )
        db.commit()
        raise error

    provider = str(result["provider"])
    selected_model = str(result["model"])
    answer = str(result["answer"])
    usage_payload = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    fallback_used = bool(budget_reason) or provider != provider_order[0]
    notice = _fallback_notice(provider, provider_order[0]) if fallback_used else ""

    usage = record_usage(
        db,
        workspace_id=ws.id,
        user_id=user_id,
        project_id=payload.project_id,
        provider=provider,
        model=selected_model,
        operation="voice.chat",
        counts=token_counts_from_usage(usage_payload),
        source="local-reported" if provider == "ollama" else "provider-reported",
    )
    if fallback_used:
        record(
            db,
            workspace_id=ws.id,
            project_id=payload.project_id,
            actor=actor,
            action="voice.chat_fallback",
            details={
                "provider": provider,
                "model": selected_model,
                "primary_provider": provider_order[0],
                "budget_blocked_paid_providers": bool(budget_reason),
                "attempts": attempts[-MAX_PROVIDER_ATTEMPTS_LOGGED:],
            },
        )
    record(
        db,
        workspace_id=ws.id,
        project_id=payload.project_id,
        actor=actor,
        action="voice.chat_replied",
        details={
            "provider": provider,
            "model": selected_model,
            "fallback_used": fallback_used,
            "input_characters": len(payload.transcript),
            "output_characters": len(answer),
            "history_items": len(payload.history),
        },
    )
    db.commit()

    response_payload = {
        "reply": answer,
        "provider": provider,
        "model": selected_model,
        "fallback_used": fallback_used,
        "notice": notice,
    }
    if usage:
        response_payload["token_usage"] = serialize_usage(usage)
    return response_payload
