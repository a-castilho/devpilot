from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx


SUPPORTED_MODEL_PROVIDERS = {"openai", "anthropic", "google"}
REFERENCE_CATALOG_DATE = "2026-08-19"


class ProviderModelDiscoveryError(RuntimeError):
    """Safe provider catalog failure suitable for the UI.

    Provider response bodies and credentials must never be included in this exception.
    """


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
        raise ProviderModelDiscoveryError("Não foi possível alcançar a API do provedor.") from error

    if response.status_code in {401, 403}:
        raise ProviderModelDiscoveryError("API key rejeitada pelo provedor.")
    if response.status_code == 429:
        raise ProviderModelDiscoveryError("O provedor limitou temporariamente a consulta de modelos.")
    if response.status_code >= 400:
        raise ProviderModelDiscoveryError(
            f"O provedor recusou a consulta de modelos (HTTP {response.status_code})."
        )
    try:
        payload = response.json()
    except ValueError as error:
        raise ProviderModelDiscoveryError("O provedor retornou um catálogo inválido.") from error
    if not isinstance(payload, dict):
        raise ProviderModelDiscoveryError("O provedor retornou um catálogo inválido.")
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
            "Este provedor não oferece descoberta automática no DevPilot."
        )
    if len(api_key) < 8:
        raise ProviderModelDiscoveryError(
            "Informe uma API key válida para consultar os modelos atuais."
        )

    if provider == "openai":
        models = _openai_models(api_key, timeout_seconds)
    elif provider == "anthropic":
        models = _anthropic_models(api_key, timeout_seconds)
    else:
        models = _google_models(api_key, timeout_seconds)

    if not models:
        raise ProviderModelDiscoveryError("Nenhum modelo utilizável foi retornado pelo provedor.")
    return models
