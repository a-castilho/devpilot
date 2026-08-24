from types import SimpleNamespace

from app.voice_all_provider_routes import (
    _anthropic_response_text,
    _credential_models,
    _custom_endpoint,
    _openai_compatible_response_text,
    _provider_order,
)


class _ScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _FakeDb:
    def __init__(self, enabled):
        self.enabled = enabled

    def scalars(self, _query):
        return _ScalarResult(self.enabled)


def test_provider_order_tries_registered_cloud_providers_before_ollama(monkeypatch):
    monkeypatch.setenv("DEVPILOT_VOICE_PROVIDER_ORDER", "openai,google,ollama")
    db = _FakeDb(["anthropic", "custom"])
    assert _provider_order(db, "workspace") == [
        "openai",
        "google",
        "anthropic",
        "custom",
        "ollama",
    ]


def test_provider_order_keeps_ollama_last_even_if_configured_first(monkeypatch):
    monkeypatch.setenv("DEVPILOT_VOICE_PROVIDER_ORDER", "ollama,google")
    db = _FakeDb(["anthropic"])
    assert _provider_order(db, "workspace") == ["google", "anthropic", "ollama"]


def test_credential_models_prefers_saved_models_and_deduplicates_defaults():
    item = SimpleNamespace(models='["model-a","model-b","model-a"]')
    assert _credential_models(item, ("model-b", "model-c")) == [
        "model-a",
        "model-b",
        "model-c",
    ]


def test_anthropic_response_text_reads_text_blocks():
    assert _anthropic_response_text(
        {
            "content": [
                {"type": "text", "text": "Resposta"},
                {"type": "tool_use", "name": "ignore"},
                {"type": "text", "text": "Anthropic"},
            ]
        }
    ) == "Resposta Anthropic"


def test_openai_compatible_response_text_reads_chat_completion():
    assert _openai_compatible_response_text(
        {"choices": [{"message": {"content": "Resposta Groq"}}]}
    ) == "Resposta Groq"


def test_custom_endpoint_recognizes_groq_connection():
    item = SimpleNamespace(provider="custom", label="Groq grátis")
    assert _custom_endpoint(item) == (
        "groq",
        "https://api.groq.com/openai/v1/chat/completions",
    )


def test_custom_endpoint_recognizes_openrouter_connection():
    item = SimpleNamespace(provider="custom", label="OpenRouter fallback")
    assert _custom_endpoint(item) == (
        "openrouter",
        "https://openrouter.ai/api/v1/chat/completions",
    )
