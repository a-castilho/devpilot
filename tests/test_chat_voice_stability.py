import asyncio
from pathlib import Path

import httpx
import pytest

from app.services.chat_http_client import (
    ChatProviderClient,
    chat_provider_request_seconds,
    chat_total_provider_seconds,
)


ROOT = Path(__file__).resolve().parents[1]


def test_voice_stability_module_is_loaded_last_in_voice_bundle():
    loader = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
    voice_bundle = loader.split("voice: [", 1)[1].split("],", 1)[0]

    assert "voice-chatgpt-layout.js" in voice_bundle
    assert "voice-runtime-stability.js" in voice_bundle
    assert voice_bundle.rfind("voice-runtime-stability.js") > voice_bundle.rfind("mobile-chat-project-picker.js")


def test_voice_stability_preserves_layout_and_recovers_transcription_422():
    source = (ROOT / "app/static/voice-runtime-stability.js").read_text(encoding="utf-8")

    assert "stopImmediatePropagation" in source
    assert "window.devpilotVoiceConversationSubmit" in source
    assert "'/api/voice/transcriptions'" in source
    assert "response.status === 422" in source
    assert "Continuo ouvindo" in source
    assert "createElement('style')" not in source
    assert ".innerHTML =" not in source


def test_chat_provider_time_budgets_are_clamped(monkeypatch):
    monkeypatch.setenv("DEVPILOT_CHAT_TOTAL_PROVIDER_SECONDS", "999")
    monkeypatch.setenv("DEVPILOT_CHAT_PROVIDER_REQUEST_SECONDS", "0.1")

    assert chat_total_provider_seconds() == 90.0
    assert chat_provider_request_seconds() == 2.0


def test_chat_provider_client_fails_fast_after_total_budget():
    async def run():
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
        client = ChatProviderClient(
            output_token_limit=320,
            transport=transport,
        )
        client._provider_deadline = -1.0
        try:
            with pytest.raises(httpx.ReadTimeout):
                await client.post("https://example.invalid/chat", json={"max_tokens": 10})
        finally:
            await client.aclose()

    asyncio.run(run())
