from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from urllib.parse import quote

import httpx


class ProviderRuntimeError(RuntimeError):
    """Sanitized provider execution failure safe to show in the dashboard."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


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
        raise ProviderRuntimeError(
            "Não foi possível alcançar a API do provedor.", retryable=True
        ) from error

    latency_ms = max(0, int((time.monotonic() - started) * 1000))
    if response.status_code in {401, 403}:
        raise ProviderRuntimeError("A credencial foi rejeitada pelo provedor.")
    if response.status_code == 429:
        raise ProviderRuntimeError(
            "O provedor limitou temporariamente a chamada.", retryable=True
        )
    if response.status_code >= 500:
        raise ProviderRuntimeError(
            f"O provedor falhou temporariamente (HTTP {response.status_code}).",
            retryable=True,
        )
    if response.status_code >= 400:
        raise ProviderRuntimeError(f"O provedor recusou a chamada (HTTP {response.status_code}).")
    try:
        data = response.json()
    except ValueError as error:
        raise ProviderRuntimeError("O provedor retornou uma resposta inválida.") from error
    if not isinstance(data, dict):
        raise ProviderRuntimeError("O provedor retornou uma resposta inválida.")
    return data, latency_ms


def _split_messages(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    system_parts: list[str] = []
    conversation: list[dict[str, str]] = []
    for item in messages:
        role = str(item.get("role", "user")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if role in {"system", "developer"}:
            system_parts.append(content)
        else:
            conversation.append({"role": role, "content": content})
    return "\n\n".join(system_parts), conversation


def _extract_openai_text(data: dict) -> str:
    texts: list[str] = []
    for output in data.get("output", []):
        if not isinstance(output, dict):
            continue
        for item in output.get("content", []):
            if isinstance(item, dict) and item.get("type") == "output_text" and item.get("text"):
                texts.append(str(item["text"]))
    return " ".join(texts).strip()


def _openai_chat(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_seconds: float,
    max_output_tokens: int,
) -> ProviderRuntimeResult:
    system, conversation = _split_messages(messages)
    payload: dict = {
        "model": model,
        "input": conversation or [{"role": "user", "content": "Respond briefly."}],
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    if system:
        payload["instructions"] = system
    data, latency_ms = _post_json(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}"},
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    reply = _extract_openai_text(data)
    if not reply:
        raise ProviderRuntimeError("O modelo respondeu sem texto utilizável.")
    return ProviderRuntimeResult("openai", model, reply[:20_000], latency_ms)


def _extract_anthropic_text(data: dict) -> str:
    texts = [
        str(item.get("text"))
        for item in data.get("content", [])
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
    ]
    return " ".join(texts).strip()


def _anthropic_chat(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_seconds: float,
    max_output_tokens: int,
) -> ProviderRuntimeResult:
    system, conversation = _split_messages(messages)
    normalized = [
        {
            "role": "assistant" if item["role"] == "assistant" else "user",
            "content": item["content"],
        }
        for item in conversation
    ]
    payload: dict = {
        "model": model,
        "max_tokens": max_output_tokens,
        "messages": normalized or [{"role": "user", "content": "Respond briefly."}],
    }
    if system:
        payload["system"] = system
    data, latency_ms = _post_json(
        "https://api.anthropic.com/v1/messages",
        headers={"X-Api-Key": api_key, "anthropic-version": "2023-06-01"},
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    reply = _extract_anthropic_text(data)
    if not reply:
        raise ProviderRuntimeError("O modelo respondeu sem texto utilizável.")
    return ProviderRuntimeResult("anthropic", model, reply[:20_000], latency_ms)


def _google_generation_config(model: str, max_output_tokens: int) -> dict:
    """Keep AgentOS calls bounded while respecting Gemini thinking controls."""

    config: dict = {"maxOutputTokens": max_output_tokens}
    normalized = model.lower()
    if normalized.startswith("gemini-3"):
        config["thinkingConfig"] = {"thinkingLevel": "low"}
    else:
        config["temperature"] = 0
        if normalized.startswith("gemini-2.5-flash"):
            config["thinkingConfig"] = {"thinkingBudget": 0}
        elif normalized.startswith("gemini-2.5-pro"):
            config["thinkingConfig"] = {"thinkingBudget": 128}
    return config


def _extract_google_text(data: dict) -> str:
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
    return " ".join(texts).strip()


def _google_chat(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout_seconds: float,
    max_output_tokens: int,
) -> ProviderRuntimeResult:
    system, conversation = _split_messages(messages)
    contents = [
        {
            "role": "model" if item["role"] == "assistant" else "user",
            "parts": [{"text": item["content"]}],
        }
        for item in conversation
    ]
    payload: dict = {
        "contents": contents or [{"role": "user", "parts": [{"text": "Respond briefly."}]}],
        "generationConfig": _google_generation_config(model, max_output_tokens),
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}
    safe_model = quote(model, safe="")
    data, latency_ms = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent",
        headers={"x-goog-api-key": api_key},
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    reply = _extract_google_text(data)
    if not reply:
        raise ProviderRuntimeError("O modelo respondeu sem texto utilizável.")
    return ProviderRuntimeResult("google", model, reply[:20_000], latency_ms)


def run_provider_chat(
    provider: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    *,
    timeout_seconds: float = 60.0,
    max_output_tokens: int = 1200,
) -> ProviderRuntimeResult:
    """Run a bounded text chat through a supported saved provider credential."""

    provider = provider.strip().lower()
    api_key = api_key.strip()
    model = model.strip()
    if provider not in {"openai", "anthropic", "google"}:
        raise ProviderRuntimeError("Este provedor não oferece execução automática no DevPilot.")
    if len(api_key) < 8:
        raise ProviderRuntimeError("A conexão não possui uma credencial válida.")
    if not model:
        raise ProviderRuntimeError("A conexão não possui um modelo configurado.")
    if max_output_tokens < 1 or max_output_tokens > 8_192:
        raise ProviderRuntimeError("Limite de saída inválido para a chamada de IA.")

    if provider == "openai":
        return _openai_chat(api_key, model, messages, timeout_seconds, max_output_tokens)
    if provider == "anthropic":
        return _anthropic_chat(api_key, model, messages, timeout_seconds, max_output_tokens)
    return _google_chat(api_key, model, messages, timeout_seconds, max_output_tokens)


def run_provider_connection_test(
    provider: str,
    api_key: str,
    model: str,
    *,
    timeout_seconds: float = 20.0,
) -> ProviderRuntimeResult:
    result = run_provider_chat(
        provider,
        api_key,
        model,
        [{"role": "user", "content": "Reply only with DEVPILOT_OK."}],
        timeout_seconds=timeout_seconds,
        max_output_tokens=256,
    )
    if "DEVPILOT_OK" not in result.reply:
        raise ProviderRuntimeError("O modelo respondeu, mas o handshake do DevPilot foi inesperado.")
    return result
