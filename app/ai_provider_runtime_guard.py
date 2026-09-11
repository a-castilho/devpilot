from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException


def _explicit_ollama_urls() -> list[str]:
    values: list[str] = []
    for name in ("DEVPILOT_OLLAMA_BASE_URLS", "DEVPILOT_OLLAMA_BASE_URL"):
        raw = str(os.getenv(name, "") or "").strip()
        if not raw:
            continue
        parts = raw.split(",") if name.endswith("URLS") else [raw]
        for value in parts:
            normalized = value.strip().rstrip("/")
            if normalized and normalized not in values:
                values.append(normalized)
    return values


def _is_cloud_runtime() -> bool:
    env = str(os.getenv("DEVPILOT_ENV", "") or "").strip().lower()
    return bool(
        env in {"homologation", "production", "staging"}
        or os.getenv("RENDER")
        or os.getenv("RENDER_SERVICE_ID")
        or os.getenv("RENDER_EXTERNAL_URL")
    )


def _attempt_code(item: dict[str, Any]) -> str:
    return str(item.get("error_code") or item.get("error_type") or "").strip().lower()


def _provider_failure(attempts: list[dict]) -> HTTPException:
    by_provider: dict[str, list[dict]] = {}
    for item in attempts:
        provider = str(item.get("provider") or "unknown").strip().lower()
        by_provider.setdefault(provider, []).append(item)

    external = [item for item in attempts if item.get("provider") in {"openai", "google", "anthropic", "custom"}]
    configured_external = [item for item in external if _attempt_code(item) != "not_configured"]
    missing = [
        provider
        for provider in ("openai", "google", "anthropic", "custom")
        if provider in by_provider and all(_attempt_code(item) == "not_configured" for item in by_provider[provider])
    ]

    if external and not configured_external:
        names = {"openai": "OpenAI", "google": "Gemini", "anthropic": "Anthropic", "custom": "Custom"}
        missing_text = ", ".join(names.get(item, item) for item in missing) or "provedor remoto"
        return HTTPException(
            503,
            f"Nenhum provedor de IA remoto está configurado ({missing_text}). Cadastre uma API key ativa em Modelos de IA. "
            "O DevPilot não tentará Ollama local dentro da Render sem uma URL Ollama explicitamente configurada.",
        )

    quota_fragments = (
        "credit_balance_exhausted",
        "no credits remaining",
        "insufficient_quota",
        "billing_hard_limit",
        "billing limit",
        "quota exceeded",
        "exceeded your current quota",
    )
    for item in configured_external:
        text = " ".join(str(item.get(key) or "").lower() for key in ("error_code", "error_type", "message"))
        if any(fragment in text for fragment in quota_fragments):
            provider = str(item.get("provider") or "provedor").title()
            return HTTPException(
                402,
                f"{provider} está configurado e a API key foi reconhecida, mas a conta está sem créditos/cota disponível. "
                "Adicione créditos ou habilite faturamento no provedor; trocar de modelo não corrige falta de saldo.",
            )

    auth_failures = [item for item in configured_external if int(item.get("status") or 0) in {401, 403}]
    if auth_failures:
        providers = sorted({str(item.get("provider") or "").title() for item in auth_failures})
        return HTTPException(502, f"Credencial de IA recusada por: {', '.join(providers)}. Atualize a API key em Modelos de IA.")

    model_failures = [item for item in configured_external if int(item.get("status") or 0) in {400, 404}]
    if model_failures:
        sample = model_failures[-1]
        provider = str(sample.get("provider") or "provedor")
        model = str(sample.get("model") or "modelo")
        detail = str(sample.get("message") or sample.get("error_code") or "modelo indisponível")[:240]
        return HTTPException(502, f"{provider} recusou o modelo {model}: {detail}. O DevPilot tentou os demais fallbacks disponíveis.")

    network_failures = [item for item in attempts if _attempt_code(item) in {"network_error", "unreachable"}]
    if network_failures and len(network_failures) == len(attempts):
        return HTTPException(503, "Os provedores configurados não estão alcançáveis a partir do backend. Verifique rede, endpoint e disponibilidade dos serviços.")

    details: list[str] = []
    for item in attempts[-6:]:
        provider = str(item.get("provider") or "?")
        code = str(item.get("error_code") or item.get("status") or "falha")
        model = str(item.get("model") or "")
        text = f"{provider}:{model}:{code}" if model else f"{provider}:{code}"
        if text not in details:
            details.append(text)
    suffix = "; ".join(details)
    return HTTPException(502, "Nenhum provedor conseguiu responder" + (f". Diagnóstico: {suffix}" if suffix else "."))


async def _cloud_safe_ollama(original, client, input_text: str, instructions: str):
    if _is_cloud_runtime() and not _explicit_ollama_urls():
        return None, [{"provider": "ollama", "model": "", "status": 0, "error_code": "not_configured", "message": "Ollama local não é alcançável na Render sem endpoint explícito."}]
    return await original(client, input_text, instructions)


def install_ai_provider_runtime_guard() -> None:
    from app import chat_mode_routes, voice_all_provider_routes, voice_conversation_routes

    original_ollama = voice_conversation_routes._try_ollama

    async def guarded_ollama(client, input_text: str, instructions: str):
        return await _cloud_safe_ollama(original_ollama, client, input_text, instructions)

    voice_conversation_routes._provider_failure = _provider_failure
    voice_conversation_routes._try_ollama = guarded_ollama

    chat_mode_routes._provider_failure = _provider_failure
    chat_mode_routes._try_ollama = guarded_ollama

    voice_all_provider_routes._provider_failure = _provider_failure
    voice_all_provider_routes._try_ollama = guarded_ollama


install_ai_provider_runtime_guard()
