from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agentos.application.errors import ModelUnavailable
from app.agentos.infrastructure import adapters
from app.agentos.infrastructure.adapters import ConfiguredLanguageModelAdapter
from app.db import Base
from app.models import ProviderCredential, Workspace
from app.services.provider_runtime import ProviderRuntimeError, ProviderRuntimeResult
from app.services.vault import Vault


class FakeOllama:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        return {"content": "local", "provider": "ollama", "model": "gemma3:1b"}


def settings(**overrides):
    values = {
        "agentos_model_provider": "google",
        "agentos_model_connection_label": "Gemini Principal",
        "agentos_model_name": "gemini-3.6-flash",
        "agentos_model_fallback": "",
        "agentos_model_max_output_tokens": 1200,
        "model_timeout_seconds": 60.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def session_with_google_connection() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    ws = Workspace(name="DevPilot", slug="default")
    db.add(ws)
    db.flush()
    db.add(
        ProviderCredential(
            workspace_id=ws.id,
            provider="google",
            label="Gemini Principal",
            encrypted_secret=Vault().encrypt("google-secret-value"),
            models=json.dumps(["gemini-2.5-flash", "gemini-3.6-flash"]),
            enabled=True,
        )
    )
    db.commit()
    return db


def test_agentos_gateway_uses_saved_google_connection_and_selected_model(monkeypatch):
    db = session_with_google_connection()
    ollama = FakeOllama()
    captured = {}
    monkeypatch.setattr(adapters, "get_settings", lambda: settings())

    def fake_chat(provider, api_key, model, messages, **kwargs):
        captured.update(
            provider=provider,
            api_key=api_key,
            model=model,
            messages=messages,
            kwargs=kwargs,
        )
        return ProviderRuntimeResult(
            provider="google",
            model="gemini-3.6-flash",
            reply="resposta externa",
            latency_ms=321,
        )

    monkeypatch.setattr(adapters, "run_provider_chat", fake_chat)
    gateway = ConfiguredLanguageModelAdapter(db, ollama=ollama)
    result = gateway.chat([{"role": "user", "content": "analise"}])

    assert result == {
        "content": "resposta externa",
        "provider": "google",
        "model": "gemini-3.6-flash",
        "latency_ms": 321,
    }
    assert captured["provider"] == "google"
    assert captured["api_key"] == "google-secret-value"
    assert captured["model"] == "gemini-3.6-flash"
    assert captured["kwargs"]["max_output_tokens"] == 1200
    assert ollama.calls == 0
    db.close()


def test_agentos_gateway_falls_back_to_ollama_only_for_transient_failure(monkeypatch):
    db = session_with_google_connection()
    ollama = FakeOllama()
    monkeypatch.setattr(
        adapters,
        "get_settings",
        lambda: settings(agentos_model_fallback="ollama"),
    )
    monkeypatch.setattr(
        adapters,
        "run_provider_chat",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ProviderRuntimeError("temporário", retryable=True)
        ),
    )

    result = ConfiguredLanguageModelAdapter(db, ollama=ollama).chat(
        [{"role": "user", "content": "analise"}]
    )

    assert result["provider"] == "ollama"
    assert result["fallback_from"] == "google"
    assert result["fallback_reason"] == "transient_provider_failure"
    assert ollama.calls == 1
    db.close()


def test_agentos_gateway_fails_closed_for_credential_or_provider_error(monkeypatch):
    db = session_with_google_connection()
    ollama = FakeOllama()
    monkeypatch.setattr(
        adapters,
        "get_settings",
        lambda: settings(agentos_model_fallback="ollama"),
    )
    monkeypatch.setattr(
        adapters,
        "run_provider_chat",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ProviderRuntimeError("credencial rejeitada", retryable=False)
        ),
    )

    with pytest.raises(ModelUnavailable, match="credencial rejeitada"):
        ConfiguredLanguageModelAdapter(db, ollama=ollama).chat(
            [{"role": "user", "content": "analise"}]
        )

    assert ollama.calls == 0
    db.close()


def test_agentos_gateway_rejects_model_not_saved_on_connection(monkeypatch):
    db = session_with_google_connection()
    ollama = FakeOllama()
    monkeypatch.setattr(
        adapters,
        "get_settings",
        lambda: settings(agentos_model_name="gemini-model-not-saved"),
    )
    called = False

    def fake_chat(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("network must not be called")

    monkeypatch.setattr(adapters, "run_provider_chat", fake_chat)

    with pytest.raises(ModelUnavailable, match="não pertence à conexão"):
        ConfiguredLanguageModelAdapter(db, ollama=ollama).chat(
            [{"role": "user", "content": "analise"}]
        )

    assert called is False
    assert ollama.calls == 0
    db.close()
