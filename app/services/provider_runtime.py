from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from urllib.parse import quote

import httpx


class ProviderRuntimeError(RuntimeError):
    """Sanitized provider execution failure safe to show in the dashboard."""


@dataclass(frozen=True, slots=True)
class ProviderRuntimeResult:
    provider: str
    model: str
    reply: str
    latency_ms: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict,
    timeout_seconds: float,
) -> tuple[dict, int]:
    started = time.monotonic()
    try:
        response = httpx.post(
            url,
            headers={"Accept": "application/json", "Content-Type": "application/json", **headers},
            json=payload,
            timeout=timeout_seconds,
            follow_redirects=False,
        )
    except httpx.RequestError as error:
        raise ProviderRuntimeError("Não foi possível alcançar a API do provedor.") from error

    latency_ms = max(0, int((time.monotonic() - started) * 1000))
    if response.status_code in {401, 403}:
        raise ProviderRuntimeError("A credencial foi rejeitada pelo provedor.")
    if response.status_code == 429:
        raise ProviderRuntimeError("O provedor limitou temporariamente a chamada de teste.")
    if response.status_code >= 400:
        raise ProviderRuntimeError(
            f"O provedor recusou a chamada de teste (HTTP {response.status_code})."
        )
    try:
        data = response.json()
    except ValueError as error:
        raise ProviderRuntimeError("O provedor retornou uma resposta inválida.") from error
    if not isinstance(data, dict):
        raise ProviderRuntimeError("O provedor retornou uma resposta inválida.")
    return data, latency_ms


def _openai_reply(api_key: str, model: str, timeout_seconds: float) -> ProviderRuntimeResult:
    data, latency_ms = _post_json(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}"},
        payload={
            "model": model,
            "input": "Reply only with DEVPILOT_OK.",
            "max_output_tokens": 16,
        },
        timeout_seconds=timeout_seconds,
    )
    texts: list[str] = []
    for output in data.get("output", []):
        if not isinstance(output, dict):
            continue
        for item in output.get("content", []):
            if isinstance(item, dict) and item.get("type") == "output_text" and item.get("text"):
                texts.append(str(item["text"]))
    reply = " ".join(texts).strip()
    if not reply:
        raise ProviderRuntimeError("O modelo respondeu sem texto utilizável.")
    return ProviderRuntimeResult("openai", model, reply[:500], latency_ms)


def _anthropic_reply(api_key: str, model: str, timeout_seconds: float) -> ProviderRuntimeResult:
    data, latency_ms = _post_json(
        "https://api.anthropic.com/v1/messages",
        headers={"X-Api-Key": api_key, "anthropic-version": "2023-06-01"},
        payload={
            "model": model,
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "Reply only with DEVPILOT_OK."}],
        },
        timeout_seconds=timeout_seconds,
    )
    texts = [
        str(item.get("text"))
        for item in data.get("content", [])
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
    ]
    reply = " ".join(texts).strip()
    if not reply:
        raise ProviderRuntimeError("O modelo respondeu sem texto utilizável.")
    return ProviderRuntimeResult("anthropic", model, reply[:500], latency_ms)


def _google_generation_config(model: str) -> dict:
    """Use a small but realistic text budget for provider health checks.

    Gemini reasoning tokens share the generation budget. A 16-token ceiling can therefore yield a
    successful HTTP response with no final text on thinking-capable models. Keep the handshake
    inexpensive while explicitly constraining reasoning according to the model family.
    """

    config: dict = {"maxOutputTokens": 256, "temperature": 0}
    normalized = model.lower()
    if normalized.startswith("gemini-3"):
        # Gemini 3 family uses thinking levels. `low` is broadly supported by the text models and
        # is sufficient for this fixed health-check prompt.
        config["thinkingConfig"] = {"thinkingLevel": "low"}
    elif normalized.startswith("gemini-2.5-flash"):
        # Gemini 2.5 Flash supports disabling thinking entirely, which is ideal for a handshake.
        config["thinkingConfig"] = {"thinkingBudget": 0}
    elif normalized.startswith("gemini-2.5-pro"):
        # 2.5 Pro cannot disable thinking; 128 is the documented minimum budget.
        config["thinkingConfig"] = {"thinkingBudget": 128}
    return config


def _google_reply(api_key: str, model: str, timeout_seconds: float) -> ProviderRuntimeResult:
    safe_model = quote(model, safe="")
    data, latency_ms = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent",
        headers={"x-goog-api-key": api_key},
        payload={
            "contents": [{"role": "user", "parts": [{"text": "Reply only with DEVPILOT_OK."}]}],
            "generationConfig": _google_generation_config(model),
        },
        timeout_seconds=timeout_seconds,
    )
    texts: list[str] = []
    for candidate in data.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        if not isinstance(content, dict):
            continue
        for part in content.get("parts", []):
            if isinstance(part, dict) and part.get("text"):
                texts.append(str(part["text"]))
    reply = " ".join(texts).strip()
    if not reply:
        raise ProviderRuntimeError("O modelo respondeu sem texto utilizável.")
    return ProviderRuntimeResult("google", model, reply[:500], latency_ms)


def run_provider_connection_test(
    provider: str,
    api_key: str,
    model: str,
    *,
    timeout_seconds: float = 20.0,
) -> ProviderRuntimeResult:
    provider = provider.strip().lower()
    api_key = api_key.strip()
    model = model.strip()
    if provider not in {"openai", "anthropic", "google"}:
        raise ProviderRuntimeError("Este provedor não oferece teste automático no DevPilot.")
    if len(api_key) < 8:
        raise ProviderRuntimeError("A conexão não possui uma credencial válida.")
    if not model:
        raise ProviderRuntimeError("A conexão não possui um modelo configurado.")

    if provider == "openai":
        return _openai_reply(api_key, model, timeout_seconds)
    if provider == "anthropic":
        return _anthropic_reply(api_key, model, timeout_seconds)
    return _google_reply(api_key, model, timeout_seconds)
