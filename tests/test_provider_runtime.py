from __future__ import annotations

import httpx
import pytest

from app.services import provider_runtime
from app.services.provider_runtime import ProviderRuntimeError, test_provider_connection


def response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_google_provider_executes_real_generate_content_shape(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(
            200,
            {
                "candidates": [
                    {"content": {"parts": [{"text": "DEVPILOT_OK"}]}}
                ]
            },
        )

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    result = test_provider_connection("google", "google-secret", "gemini-2.5-flash")

    assert result.provider == "google"
    assert result.model == "gemini-2.5-flash"
    assert result.reply == "DEVPILOT_OK"
    assert captured["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert captured["headers"]["x-goog-api-key"] == "google-secret"
    assert "google-secret" not in captured["url"]
    assert captured["json"]["generationConfig"]["maxOutputTokens"] == 16


def test_openai_provider_uses_responses_api(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(
            200,
            {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "DEVPILOT_OK"}],
                    }
                ]
            },
        )

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    result = test_provider_connection("openai", "sk-test-key", "gpt-5.6")

    assert result.reply == "DEVPILOT_OK"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-key"
    assert captured["json"]["max_output_tokens"] == 16


def test_anthropic_provider_uses_messages_api(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(200, {"content": [{"type": "text", "text": "DEVPILOT_OK"}]})

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    result = test_provider_connection("anthropic", "anthropic-secret", "claude-sonnet")

    assert result.reply == "DEVPILOT_OK"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["X-Api-Key"] == "anthropic-secret"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["max_tokens"] == 16


def test_runtime_auth_failure_does_not_leak_provider_body(monkeypatch):
    monkeypatch.setattr(
        provider_runtime.httpx,
        "post",
        lambda *args, **kwargs: response(
            401,
            {"error": {"message": "account-sensitive-private-detail"}},
        ),
    )

    with pytest.raises(ProviderRuntimeError, match="credencial foi rejeitada") as caught:
        test_provider_connection("google", "secret-key", "gemini-2.5-flash")

    assert "account-sensitive-private-detail" not in str(caught.value)


def test_runtime_rejects_unknown_provider_without_network(monkeypatch):
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        return response(200, {})

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    with pytest.raises(ProviderRuntimeError, match="não oferece teste automático"):
        test_provider_connection("custom", "custom-secret", "model-a")
    assert not called
