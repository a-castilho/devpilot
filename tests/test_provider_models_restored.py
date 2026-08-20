from __future__ import annotations

import httpx
import pytest

from app.services import provider_models
from app.services.provider_models import ProviderModelDiscoveryError, discover_provider_models


def response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_openai_discovers_account_models(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(200, {"data": [{"id": "gpt-z"}, {"id": "gpt-a"}, {"id": "gpt-a"}]})

    monkeypatch.setattr(provider_models.httpx, "get", fake_get)
    models = discover_provider_models("openai", "sk-test-key")

    assert [item.id for item in models] == ["gpt-a", "gpt-z"]
    assert captured["url"] == "https://api.openai.com/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-key"


def test_anthropic_preserves_provider_order(monkeypatch):
    def fake_get(url, **kwargs):
        assert kwargs["headers"]["X-Api-Key"] == "anthropic-secret"
        assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
        return response(
            200,
            {
                "data": [
                    {"id": "claude-new", "display_name": "Claude New"},
                    {"id": "claude-old", "display_name": "Claude Old"},
                ]
            },
        )

    monkeypatch.setattr(provider_models.httpx, "get", fake_get)
    models = discover_provider_models("anthropic", "anthropic-secret")
    assert [(item.id, item.label) for item in models] == [
        ("claude-new", "Claude New"),
        ("claude-old", "Claude Old"),
    ]


def test_google_uses_header_key_and_excludes_embedding_only(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(
            200,
            {
                "models": [
                    {
                        "name": "models/gemini-live",
                        "displayName": "Gemini Live",
                        "supportedGenerationMethods": ["bidiGenerateContent"],
                    },
                    {
                        "name": "models/gemini-chat",
                        "displayName": "Gemini Chat",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-embedding",
                        "displayName": "Gemini Embedding",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ]
            },
        )

    monkeypatch.setattr(provider_models.httpx, "get", fake_get)
    models = discover_provider_models("google", "google-secret")

    assert [item.id for item in models] == ["gemini-live", "gemini-chat"]
    assert captured["headers"]["x-goog-api-key"] == "google-secret"
    assert "google-secret" not in captured["url"]


def test_provider_auth_error_does_not_expose_response_body(monkeypatch):
    monkeypatch.setattr(
        provider_models.httpx,
        "get",
        lambda *args, **kwargs: response(401, {"error": {"message": "sensitive account detail"}}),
    )

    with pytest.raises(ProviderModelDiscoveryError, match="API key rejeitada") as caught:
        discover_provider_models("openai", "sk-invalid")

    assert "sensitive account detail" not in str(caught.value)


def test_custom_provider_requires_manual_catalog():
    with pytest.raises(ProviderModelDiscoveryError, match="não oferece descoberta automática"):
        discover_provider_models("custom", "custom-secret")
