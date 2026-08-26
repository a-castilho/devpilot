from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import httpx


SUPPORTED_MODEL_PROVIDERS = {"openai", "anthropic", "google"}
REFERENCE_CATALOG_DATE = "2026-08-19"


class ProviderModelDiscoveryError(RuntimeError):
    """Safe provider catalog failure suitable for the UI.

    Provider response bodies and credentials must never be included in this exception.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        upstream_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.upstream_status = upstream_status


@dataclass(frozen=True, slots=True)
class ProviderModel:
    id: str
    label: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


REFERENCE_MODEL_CATALOG: dict[str, tuple[ProviderModel, ...]] = {
    "openai": (
        ProviderModel("gpt-5.6-sol", "GPT-5.6 Sol"),
        ProviderModel("gpt-5.6-terra", "GPT-5.6 Terra"),
        ProviderModel("gpt-5.6-luna", "GPT-5.6 Luna"),
        ProviderModel("gpt-5.5", "GPT-5.5"),
        ProviderModel("gpt-5.5-pro", "GPT-5.5 Pro"),
        ProviderModel("gpt-5.4", "GPT-5.4"),
        ProviderModel("gpt-5.4-pro", "GPT-5.4 Pro"),
        ProviderModel("gpt-5.4-mini", "GPT-5.4 Mini"),
        ProviderModel("gpt-5.4-nano", "GPT-5.4 Nano"),
        ProviderModel("gpt-realtime-2.1", "GPT Realtime 2.1"),
    ),
    "anthropic": (
        ProviderModel("claude-fable-5", "Claude Fable 5"),
        ProviderModel("claude-opus-5", "Claude Opus 5"),
        ProviderModel("claude-sonnet-5", "Claude Sonnet 5"),
        ProviderModel("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
    ),
    "google": (
        ProviderModel("gemini-3.6-flash", "Gemini 3.6 Flash"),
        ProviderModel("gemini-3.5-flash", "Gemini 3.5 Flash"),
        ProviderModel("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
        ProviderModel("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite"),
        ProviderModel("gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview"),
        ProviderModel("gemini-3-flash-preview", "Gemini 3 Flash Preview"),
        ProviderModel("gemini-2.5-pro", "Gemini 2.5 Pro"),
        ProviderModel("gemini-2.5-flash", "Gemini 2.5 Flash"),
        ProviderModel("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite"),
        ProviderModel("gemini-3.1-flash-live-preview", "Gemini 3.1 Flash Live Preview"),
    ),
}

_OPENAI_TEXT_MODEL = re.compile(r"^(?:gpt-|o\d|codex)", re.IGNORECASE)
_OPENAI_NON_TEXT_HINTS = (
    "audio",
    "embedding",
    "image",
    "moderation",
    "realtime",
    "search",
    "transcrib",
    "tts",
    "whisper",
)


def reference_provider_models(provider: str) -> list[ProviderModel]:
    return list(REFERENCE_MODEL_CATALOG.get(provider.strip().lower(), ()))


def _dedupe(models: list[ProviderModel]) -> list[ProviderModel]:
    seen: set[str] = set()
    result: list[ProviderModel] = []
    for model in models:
        model_id = model.id.strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        result.append(ProviderModel(id=model_id, label=model.label.strip() or model_id))
    return result


def _is_recommended_candidate(provider: str, model: ProviderModel) -> bool:
    if provider != "openai":
        return True
    model_id = model.id.casefold()
    return bool(_OPENAI_TEXT_MODEL.search(model.id)) and not any(
        hint in model_id for hint in _OPENAI_NON_TEXT_HINTS
    )


def recommended_provider_models(
    provider: str,
    models: list[ProviderModel],
    *,
    limit: int = 6,
) -> list[ProviderModel]:
    """Return a small, useful default set instead of persisting an entire provider catalog.

    Reference models are preferred when the account exposes them. If those exact model IDs are not
    available, provider-specific text/code candidates are used. The function never invents model IDs:
    every recommendation comes from the provider response supplied in ``models``.
    """
    provider = provider.strip().lower()
    available = _dedupe(models)
    if limit <= 0 or not available:
        return []

    by_id = {model.id: model for model in available}
    selected: list[ProviderModel] = []
    seen: set[str] = set()

    for reference in reference_provider_models(provider):
        model = by_id.get(reference.id)
        if model and model.id not in seen and _is_recommended_candidate(provider, model):
            selected.append(model)
            seen.add(model.id)
            if len(selected) >= limit:
                return selected

    candidates = [model for model in available if _is_recommended_candidate(provider, model)]
    if provider == "openai":
        candidates = sorted(candidates, key=lambda item: item.id.casefold(), reverse=True)

    for model in candidates:
        if model.id in seen:
            continue
        selected.append(model)
        seen.add(model.id)
        if len(selected) >= limit:
            break

    if selected:
        return selected
    return available[:limit]


def _request_json(
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, str | int] | None = None,
    timeout_seconds: float = 15.0,
) -> dict:
    try:
        response = httpx.get(
            url,
            headers={"Accept": "application/json", "User-Agent": "DevPilot/1.0", **headers},
            params=params,
            timeout=timeout_seconds,
            follow_redirects=False,
        )
    except httpx.RequestError as error:
        raise ProviderModelDiscoveryError(
            "Não foi possível alcançar a API do provedor.",
            code="provider_unreachable",
        ) from error

    if response.status_code == 401:
        raise ProviderModelDiscoveryError(
            "API key não autenticada pelo provedor. "
            "Verifique se a chave está correta, ativa e pertence ao projeto/organização esperados.",
            code="authentication_failed",
            upstream_status=401,
        )
    if response.status_code == 403:
        raise ProviderModelDiscoveryError(
            "O provedor negou acesso ao catálogo de modelos (HTTP 403). "
            "Revise as permissões da API key e do projeto para permitir a leitura do catálogo.",
            code="catalog_forbidden",
            upstream_status=403,
        )
    if response.status_code == 429:
        raise ProviderModelDiscoveryError(
            "O provedor limitou temporariamente a consulta de modelos.",
            code="rate_limited",
            upstream_status=429,
        )
    if response.status_code >= 400:
        raise ProviderModelDiscoveryError(
            f"O provedor recusou a consulta de modelos (HTTP {response.status_code}).",
            code="provider_http_error",
            upstream_status=response.status_code,
        )
    try:
        payload = response.json()
    except ValueError as error:
        raise ProviderModelDiscoveryError(
            "O provedor retornou um catálogo inválido.",
            code="invalid_catalog",
        ) from error
    if not isinstance(payload, dict):
        raise ProviderModelDiscoveryError(
            "O provedor retornou um catálogo inválido.",
            code="invalid_catalog",
        )
    return payload


def _openai_models(api_key: str, timeout_seconds: float) -> list[ProviderModel]:
    payload = _request_json(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout_seconds=timeout_seconds,
    )
    data = payload.get("data", [])
    models = [
        ProviderModel(id=str(item.get("id", "")), label=str(item.get("id", "")))
        for item in data
        if isinstance(item, dict)
    ]
    return sorted(_dedupe(models), key=lambda item: item.id.lower())


def _anthropic_models(api_key: str, timeout_seconds: float) -> list[ProviderModel]:
    payload = _request_json(
        "https://api.anthropic.com/v1/models",
        headers={
            "X-Api-Key": api_key,
            "anthropic-version": "2023-06-01",
        },
        params={"limit": 1000},
        timeout_seconds=timeout_seconds,
    )
    data = payload.get("data", [])
    models = [
        ProviderModel(
            id=str(item.get("id", "")),
            label=str(item.get("display_name") or item.get("id") or ""),
        )
        for item in data
        if isinstance(item, dict)
    ]
    return _dedupe(models)


def _google_models(api_key: str, timeout_seconds: float) -> list[ProviderModel]:
    payload = _request_json(
        "https://generativelanguage.googleapis.com/v1beta/models",
        headers={"x-goog-api-key": api_key},
        params={"pageSize": 1000},
        timeout_seconds=timeout_seconds,
    )
    data = payload.get("models", [])
    models: list[ProviderModel] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        methods = item.get("supportedGenerationMethods") or []
        if methods and "generateContent" not in methods and "bidiGenerateContent" not in methods:
            continue
        raw_id = str(item.get("name", ""))
        model_id = raw_id.removeprefix("models/")
        models.append(
            ProviderModel(
                id=model_id,
                label=str(item.get("displayName") or model_id),
            )
        )
    return _dedupe(models)


def discover_provider_models(
    provider: str,
    api_key: str,
    *,
    timeout_seconds: float = 15.0,
) -> list[ProviderModel]:
    provider = provider.strip().lower()
    api_key = api_key.strip()
    if provider not in SUPPORTED_MODEL_PROVIDERS:
        raise ProviderModelDiscoveryError(
            "Este provedor não oferece descoberta automática no DevPilot.",
            code="unsupported_provider",
        )
    if len(api_key) < 8:
        raise ProviderModelDiscoveryError(
            "Informe uma API key válida para consultar os modelos atuais.",
            code="invalid_key_format",
        )

    if provider == "openai":
        models = _openai_models(api_key, timeout_seconds)
    elif provider == "anthropic":
        models = _anthropic_models(api_key, timeout_seconds)
    else:
        models = _google_models(api_key, timeout_seconds)

    if not models:
        raise ProviderModelDiscoveryError(
            "Nenhum modelo utilizável foi retornado pelo provedor.",
            code="empty_catalog",
        )
    return models
