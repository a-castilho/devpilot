from __future__ import annotations

import asyncio
import json
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProviderCredential
from app.security import require_access
from app.services.ai_costs import budget_block_reason
from app.services.audit import record
from app.services.token_usage import (
    record_usage,
    serialize_usage,
    token_counts_from_usage,
    user_id_from_actor,
)
from app.voice_conversation_routes import (
    MAX_PROVIDER_ATTEMPTS_LOGGED,
    VoiceConversationRequest,
    _attempt,
    _chat_models,
    _conversation_input,
    _decrypt_secret,
    _instructions,
    _project_context,
    _provider_api_keys,
    _provider_error_metadata,
    _provider_failure,
    _response_text,
    _retry_delay,
    _stored_provider_models,
    _try_google,
    _try_ollama,
    _workspace,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])

REMOTE_PROVIDER_SEQUENCE = ("openai", "google", "anthropic", "custom")
SUPPORTED_FAILOVER_PROVIDERS = (*REMOTE_PROVIDER_SEQUENCE, "ollama")
DEFAULT_ANTHROPIC_CHAT_MODELS = (
    "claude-sonnet-5",
    "claude-haiku-4-5-20251001",
)


def _split_env_list(name: str) -> list[str]:
    return [value.strip() for value in os.getenv(name, "").split(",") if value.strip()]


def _enabled_credentials(
    db: Session, workspace_id: str, provider: str
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


def _credential_models(item: ProviderCredential, defaults: tuple[str, ...] = ()) -> list[str]:
    try:
        raw = json.loads(item.models or "[]")
    except (TypeError, ValueError):
        raw = []
    selected = (
        [str(value or "").strip() for value in raw]
        if isinstance(raw, list)
        else []
    )
    return list(dict.fromkeys([value for value in [*selected, *defaults] if value]))


def _provider_order(db: Session, workspace_id: str) -> list[str]:
    configured = [
        value.lower()
        for value in _split_env_list("DEVPILOT_VOICE_PROVIDER_ORDER")
        if value.lower() in SUPPORTED_FAILOVER_PROVIDERS
    ]
    enabled = set(
        db.scalars(
            select(ProviderCredential.provider).where(
                ProviderCredential.workspace_id == workspace_id,
                ProviderCredential.enabled.is_(True),
            )
        ).all()
    )

    result: list[str] = []
    # Respect configured cloud ordering, but keep Ollama as the final safety net.
    for provider in configured:
        if provider != "ollama" and provider not in result:
            result.append(provider)
    # Every enabled cloud provider must be tried even when the old environment order omits it.
    for provider in REMOTE_PROVIDER_SEQUENCE:
        if provider in enabled and provider not in result:
            result.append(provider)
    # Preserve legacy defaults if no external ordering was configured.
    if not result:
        result.extend(["openai", "google"])
    # Local Ollama is always last, after all configured/registered remote providers.
    result.append("ollama")
    return result


def _openai_compatible_response_text(data: dict) -> str:
    for choice in data.get("choices") or []:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text = " ".join(
                str(item.get("text") or "").strip()
                for item in content
                if isinstance(item, dict) and str(item.get("text") or "").strip()
            ).strip()
            if text:
                return text
    return ""


def _anthropic_response_text(data: dict) -> str:
    return " ".join(
        str(item.get("text") or "").strip()
        for item in data.get("content") or []
        if isinstance(item, dict)
        and item.get("type") == "text"
        and str(item.get("text") or "").strip()
    ).strip()


async def _try_openai_all(
    client: httpx.AsyncClient,
    db: Session,
    workspace_id: str,
    input_text: str,
    instructions: str,
) -> tuple[dict | None, list[dict]]:
    attempts: list[dict] = []
    keys = _provider_api_keys(db, workspace_id, "openai")
    if not keys:
        return None, [_attempt("openai", "", status=0, error_code="not_configured")]

    models = list(
        dict.fromkeys(
            [
                *_stored_provider_models(db, workspace_id, "openai"),
                *_chat_models(),
            ]
        )
    )
    for api_key in keys:
        for model in models:
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
                    if response.status_code == 429 and retry == 0:
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
                usage = data.get("usage")
                return {
                    "answer": answer,
                    "provider": "openai",
                    "model": model,
                    "usage": usage if isinstance(usage, dict) else {},
                }, attempts
    return None, attempts


async def _try_anthropic(
    client: httpx.AsyncClient,
    db: Session,
    workspace_id: str,
    input_text: str,
    instructions: str,
) -> tuple[dict | None, list[dict]]:
    attempts: list[dict] = []
    credentials = _enabled_credentials(db, workspace_id, "anthropic")
    env_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    candidates: list[tuple[str, list[str], str]] = []
    if env_key:
        models = list(
            dict.fromkeys(
                [
                    *_split_env_list("DEVPILOT_VOICE_ANTHROPIC_MODELS"),
                    *DEFAULT_ANTHROPIC_CHAT_MODELS,
                ]
            )
        )
        candidates.append((env_key, models, "env"))

    for item in credentials:
        secret = _decrypt_secret(item)
        if not secret:
            continue
        models = _credential_models(item, DEFAULT_ANTHROPIC_CHAT_MODELS)
        candidates.append((secret, models, item.id))

    if not candidates:
        return None, [_attempt("anthropic", "", status=0, error_code="not_configured")]

    for api_key, models, connection_id in candidates:
        for model in models:
            for retry in range(2):
                try:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": model,
                            "max_tokens": 280,
                            "system": instructions,
                            "messages": [{"role": "user", "content": input_text}],
                        },
                    )
                except httpx.HTTPError as error:
                    attempts.append(
                        _attempt(
                            "anthropic",
                            model,
                            status=502,
                            error_type=type(error).__name__,
                            error_code="network_error",
                        )
                    )
                    break

                if response.status_code >= 400:
                    metadata = _provider_error_metadata(response)
                    attempts.append(_attempt("anthropic", model, **metadata))
                    if response.status_code == 429 and retry == 0:
                        await asyncio.sleep(_retry_delay(response, retry))
                        continue
                    break

                try:
                    data = response.json()
                except ValueError:
                    attempts.append(
                        _attempt("anthropic", model, status=502, error_code="invalid_json")
                    )
                    break

                answer = _anthropic_response_text(data)
                if not answer:
                    attempts.append(
                        _attempt("anthropic", model, status=502, error_code="empty_response")
                    )
                    break
                usage = data.get("usage")
                return {
                    "answer": answer,
                    "provider": "anthropic",
                    "model": model,
                    "usage": usage if isinstance(usage, dict) else {},
                    "connection_id": connection_id,
                }, attempts
    return None, attempts


def _custom_endpoint(item: ProviderCredential) -> tuple[str, str]:
    label = f"{item.provider} {item.label}".lower()
    if "groq" in label:
        return "groq", "https://api.groq.com/openai/v1/chat/completions"
    if "openrouter" in label:
        return "openrouter", "https://openrouter.ai/api/v1/chat/completions"

    configured = os.getenv("DEVPILOT_VOICE_CUSTOM_BASE_URL", "").strip().rstrip("/")
    if configured:
        endpoint = (
            configured
            if configured.endswith("/chat/completions")
            else f"{configured}/v1/chat/completions"
        )
        return "custom", endpoint
    return "custom", ""


async def _try_custom(
    client: httpx.AsyncClient,
    db: Session,
    workspace_id: str,
    input_text: str,
    instructions: str,
) -> tuple[dict | None, list[dict]]:
    attempts: list[dict] = []
    credentials = _enabled_credentials(db, workspace_id, "custom")
    if not credentials:
        return None, [_attempt("custom", "", status=0, error_code="not_configured")]

    for item in credentials:
        provider_name, endpoint = _custom_endpoint(item)
        models = _credential_models(item)
        if not endpoint:
            attempts.append(
                _attempt(
                    provider_name,
                    item.label,
                    status=0,
                    error_code="endpoint_not_configured",
                )
            )
            continue
        if not models:
            attempts.append(
                _attempt(provider_name, item.label, status=0, error_code="no_models")
            )
            continue

        api_key = _decrypt_secret(item)
        if not api_key:
            attempts.append(
                _attempt(
                    provider_name,
                    item.label,
                    status=0,
                    error_code="credential_unavailable",
                )
            )
            continue

        for model in models:
            for retry in range(2):
                try:
                    response = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": instructions},
                                {"role": "user", "content": input_text},
                            ],
                            "max_tokens": 280,
                            "stream": False,
                        },
                    )
                except httpx.HTTPError as error:
                    attempts.append(
                        _attempt(
                            provider_name,
                            model,
                            status=502,
                            error_type=type(error).__name__,
                            error_code="network_error",
                        )
                    )
                    break

                if response.status_code >= 400:
                    metadata = _provider_error_metadata(response)
                    attempts.append(_attempt(provider_name, model, **metadata))
                    if response.status_code == 429 and retry == 0:
                        await asyncio.sleep(_retry_delay(response, retry))
                        continue
                    break

                try:
                    data = response.json()
                except ValueError:
                    attempts.append(
                        _attempt(provider_name, model, status=502, error_code="invalid_json")
                    )
                    break

                answer = _openai_compatible_response_text(data)
                if not answer:
                    attempts.append(
                        _attempt(provider_name, model, status=502, error_code="empty_response")
                    )
                    break
                usage = data.get("usage")
                return {
                    "answer": answer,
                    "provider": provider_name,
                    "model": model,
                    "usage": usage if isinstance(usage, dict) else {},
                    "connection_id": item.id,
                }, attempts
    return None, attempts


def _fallback_notice(provider: str, primary: str) -> str:
    if provider == primary:
        return ""
    names = {
        "google": "Google Gemini",
        "anthropic": "Anthropic",
        "groq": "Groq",
        "openrouter": "OpenRouter",
        "custom": "provedor customizado",
        "ollama": "Ollama local",
    }
    return f"Provedor anterior indisponível; usando {names.get(provider, provider)} automaticamente."


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
    provider_order = _provider_order(db, ws.id)
    effective_order = provider_order

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
        effective_order = ["ollama"]

    result: dict | None = None
    attempts: list[dict] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
        for provider in effective_order:
            if provider == "openai":
                candidate, provider_attempts = await _try_openai_all(
                    client, db, ws.id, input_text, instructions
                )
            elif provider == "google":
                candidate, provider_attempts = await _try_google(
                    client, db, ws.id, input_text, instructions
                )
            elif provider == "anthropic":
                candidate, provider_attempts = await _try_anthropic(
                    client, db, ws.id, input_text, instructions
                )
            elif provider == "custom":
                candidate, provider_attempts = await _try_custom(
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
                    "provider_order": effective_order,
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
                "provider_order": effective_order,
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
    primary = provider_order[0]
    fallback_used = bool(budget_reason) or provider != primary
    notice = _fallback_notice(provider, primary) if fallback_used else ""

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
                "primary_provider": primary,
                "budget_blocked_paid_providers": bool(budget_reason),
                "provider_order": effective_order,
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
            "connection_id": result.get("connection_id", ""),
            "input_characters": len(payload.transcript),
            "output_characters": len(answer),
            "history_items": len(payload.history),
        },
    )
    db.commit()

    attempted_providers: list[str] = []
    for item in attempts:
        value = str(item.get("provider") or "").strip()
        if value and value not in attempted_providers:
            attempted_providers.append(value)
    if provider not in attempted_providers:
        attempted_providers.append(provider)

    response_payload = {
        "reply": answer,
        "provider": provider,
        "model": selected_model,
        "fallback_used": fallback_used,
        "notice": notice,
        "providers_tried": attempted_providers,
    }
    if usage:
        response_payload["token_usage"] = serialize_usage(usage)
    return response_payload
