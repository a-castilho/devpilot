import httpx

from app.voice_conversation_routes import (
    _google_response_text,
    _ollama_response_text,
    _provider_error_metadata,
    _provider_order,
    _quota_exhausted,
)


def test_provider_order_defaults_to_openai_google_ollama(monkeypatch):
    monkeypatch.delenv("DEVPILOT_VOICE_PROVIDER_ORDER", raising=False)
    assert _provider_order() == ["openai", "google", "ollama"]


def test_provider_order_keeps_fallbacks_when_primary_is_overridden(monkeypatch):
    monkeypatch.setenv("DEVPILOT_VOICE_PROVIDER_ORDER", "google,ollama")
    assert _provider_order() == ["google", "ollama", "openai"]


def test_openai_quota_error_is_distinguished_from_temporary_rate_limit():
    response = httpx.Response(
        429,
        json={
            "error": {
                "type": "insufficient_quota",
                "code": "insufficient_quota",
                "message": "You exceeded your current quota.",
            }
        },
        headers={"x-request-id": "req_voice_123"},
    )
    metadata = _provider_error_metadata(response)
    assert metadata["status"] == 429
    assert metadata["request_id"] == "req_voice_123"
    assert _quota_exhausted(metadata) is True


def test_google_response_text_reads_candidate_parts():
    payload = {
        "candidates": [
            {"content": {"parts": [{"text": "Resposta"}, {"text": "do Gemini"}]}}
        ]
    }
    assert _google_response_text(payload) == "Resposta do Gemini"


def test_ollama_response_text_reads_chat_message():
    payload = {"message": {"role": "assistant", "content": "Resposta local"}}
    assert _ollama_response_text(payload) == "Resposta local"
