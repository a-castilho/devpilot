from __future__ import annotations

import os
import time

import httpx


CHAT_TEXT_DEFAULT_OUTPUT_TOKENS = 2048
CHAT_VOICE_DEFAULT_OUTPUT_TOKENS = 320
CHAT_MIN_OUTPUT_TOKENS = 256
CHAT_MAX_OUTPUT_TOKENS = 8192
CHAT_DEFAULT_TOTAL_PROVIDER_SECONDS = 40.0
CHAT_DEFAULT_PROVIDER_REQUEST_SECONDS = 20.0
CHAT_MIN_TOTAL_PROVIDER_SECONDS = 5.0
CHAT_MAX_TOTAL_PROVIDER_SECONDS = 90.0
CHAT_MIN_PROVIDER_REQUEST_SECONDS = 2.0
CHAT_MAX_PROVIDER_REQUEST_SECONDS = 45.0


def _float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def chat_total_provider_seconds() -> float:
    return _float_env(
        "DEVPILOT_CHAT_TOTAL_PROVIDER_SECONDS",
        CHAT_DEFAULT_TOTAL_PROVIDER_SECONDS,
        CHAT_MIN_TOTAL_PROVIDER_SECONDS,
        CHAT_MAX_TOTAL_PROVIDER_SECONDS,
    )


def chat_provider_request_seconds() -> float:
    return _float_env(
        "DEVPILOT_CHAT_PROVIDER_REQUEST_SECONDS",
        CHAT_DEFAULT_PROVIDER_REQUEST_SECONDS,
        CHAT_MIN_PROVIDER_REQUEST_SECONDS,
        CHAT_MAX_PROVIDER_REQUEST_SECONDS,
    )


def chat_output_token_limit(response_style: str = "chat") -> int:
    if response_style == "voice":
        env_name = "DEVPILOT_CHAT_VOICE_MAX_OUTPUT_TOKENS"
        default = CHAT_VOICE_DEFAULT_OUTPUT_TOKENS
    else:
        env_name = "DEVPILOT_CHAT_MAX_OUTPUT_TOKENS"
        default = CHAT_TEXT_DEFAULT_OUTPUT_TOKENS

    raw = os.getenv(env_name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(CHAT_MIN_OUTPUT_TOKENS, min(CHAT_MAX_OUTPUT_TOKENS, value))


def apply_chat_output_budget(payload: dict, output_token_limit: int) -> dict:
    result = dict(payload)
    if "max_output_tokens" in result:
        result["max_output_tokens"] = output_token_limit
    if "max_tokens" in result:
        result["max_tokens"] = output_token_limit

    generation = result.get("generationConfig")
    if isinstance(generation, dict):
        result["generationConfig"] = {
            **generation,
            "maxOutputTokens": output_token_limit,
        }

    options = result.get("options")
    if isinstance(options, dict):
        result["options"] = {
            **options,
            "num_predict": output_token_limit,
        }
    return result


class ChatProviderClient(httpx.AsyncClient):
    """Apply response budgets and a bounded provider wait only to /api/chat."""

    def __init__(self, *args, output_token_limit: int, **kwargs):
        super().__init__(*args, **kwargs)
        self._output_token_limit = output_token_limit
        self._provider_deadline = time.monotonic() + chat_total_provider_seconds()
        self._provider_request_seconds = chat_provider_request_seconds()

    async def post(self, url, *args, **kwargs):
        remaining = self._provider_deadline - time.monotonic()
        if remaining <= 0:
            raise httpx.ReadTimeout(
                "Tempo total de provedores do chat esgotado antes desta tentativa."
            )

        payload = kwargs.get("json")
        if isinstance(payload, dict):
            kwargs["json"] = apply_chat_output_budget(
                payload,
                self._output_token_limit,
            )

        # Cada tentativa recebe apenas a fatia ainda disponível do orçamento
        # acumulado. Assim uma credencial/modelo indisponível não deixa o chat
        # preso por minutos enquanto a cadeia de fallback continua tentando.
        kwargs["timeout"] = max(
            0.1,
            min(self._provider_request_seconds, remaining),
        )
        return await super().post(url, *args, **kwargs)
