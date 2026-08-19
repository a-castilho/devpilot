from __future__ import annotations

import httpx
import pytest

from app.services import provider_runtime
from app.services.provider_runtime import (
    ProviderRuntimeError,
    run_provider_chat,
    run_provider_connection_test,
)


def response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_google_provider_executes_real_generate_content_shape(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(
            200,
            {"candidates": [{"content": {"parts": [{"text": "DEVPILOT_OK"}]}}]},
        )

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    result = run_provider_connection_test("google", "google-secret", "gemini-2.5-flash")

    assert result.provider == "google"
    assert result.model == "gemini-2.5-flash"
    assert result.reply == "DEVPILOT_OK"
    assert captured["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert captured["headers"]["x-goog-api-key"] == "google-secret"
    assert "google-secret" not in captured["url"]
    config = captured["json"]["generationConfig"]
    assert config["maxOutputTokens"] == 256
    assert config["thinkingConfig"] == {"thinkingBudget": 0}
    assert config["temperature"] == 0


def test_google_gemini3_constrains_thinking_for_handshake(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(
            200,
            {"candidates": [{"content": {"parts": [{"text": "DEVPILOT_OK"}]}}]},
        )

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    result = run_provider_connection_test("google", "google-secret", "gemini-3.6-flash")

    assert result.reply == "DEVPILOT_OK"
    config = captured["json"]["generationConfig"]
    assert config["maxOutputTokens"] == 256
    assert config["thinkingConfig"] == {"thinkingLevel": "low"}
    assert "temperature" not in config


def test_google_25_pro_uses_minimum_thinking_budget(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(
            200,
            {"candidates": [{"content": {"parts": [{"text": "DEVPILOT_OK"}]}}]},
        )

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    run_provider_connection_test("google", "google-secret", "gemini-2.5-pro")

    assert captured["json"]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 128}


def test_google_chat_maps_system_instruction_and_conversation(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(
            200,
            {"candidates": [{"content": {"parts": [{"text": "resultado"}]}}]},
        )

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    result = run_provider_chat(
        "google",
        "google-secret",
        "gemini-3.6-flash",
        [
            {"role": "system", "content": "Siga as regras do AgentOS."},
            {"role": "user", "content": "Analise o projeto."},
        ],
        max_output_tokens=900,
    )

    assert result.reply == "resultado"
    assert captured["json"]["system_instruction"]["parts"][0]["text"] == "Siga as regras do AgentOS."
    assert captured["json"]["contents"] == [
        {"role": "user", "parts": [{"text": "Analise o projeto."}]}
    ]
    assert captured["json"]["generationConfig"]["maxOutputTokens"] == 900


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
    result = run_provider_connection_test("openai", "sk-test-key", "gpt-5.6")

    assert result.reply == "DEVPILOT_OK"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer sk-test-key"
    assert captured["json"]["max_output_tokens"] == 256
    assert captured["json"]["store"] is False


def test_anthropic_provider_uses_messages_api(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return response(200, {"content": [{"type": "text", "text": "DEVPILOT_OK"}]})

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    result = run_provider_connection_test("anthropic", "anthropic-secret", "claude-sonnet")

    assert result.reply == "DEVPILOT_OK"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["X-Api-Key"] == "anthropic-secret"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["json"]["max_tokens"] == 256


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
        run_provider_connection_test("google", "secret-key", "gemini-2.5-flash")

    assert caught.value.retryable is False
    assert "account-sensitive-private-detail" not in str(caught.value)


def test_runtime_marks_rate_limit_as_retryable(monkeypatch):
    monkeypatch.setattr(
        provider_runtime.httpx,
        "post",
        lambda *args, **kwargs: response(429, {"error": {"message": "private"}}),
    )

    with pytest.raises(ProviderRuntimeError) as caught:
        run_provider_chat(
            "google",
            "secret-key",
            "gemini-3.6-flash",
            [{"role": "user", "content": "teste"}],
        )

    assert caught.value.retryable is True
    assert "private" not in str(caught.value)


def test_connection_test_rejects_unexpected_handshake(monkeypatch):
    monkeypatch.setattr(
        provider_runtime.httpx,
        "post",
        lambda *args, **kwargs: response(
            200,
            {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]},
        ),
    )

    with pytest.raises(ProviderRuntimeError, match="handshake"):
        run_provider_connection_test("google", "secret-key", "gemini-3.6-flash")


def test_runtime_rejects_unknown_provider_without_network(monkeypatch):
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        return response(200, {})

    monkeypatch.setattr(provider_runtime.httpx, "post", fake_post)
    with pytest.raises(ProviderRuntimeError, match="não oferece execução automática"):
        run_provider_connection_test("custom", "custom-secret", "model-a")
    assert not called
