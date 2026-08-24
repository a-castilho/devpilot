from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_insecure_lan_guard_preserves_voice_fallback_and_conversation_mode():
    guard = read("app/static/voice-insecure-lan-guard.js")

    assert "return originalStart.call(startButton, event);" in guard
    assert "const startConversationMode = (event) => {" in guard
    assert "event?.preventDefault?.();" in guard
    assert "event?.stopPropagation?.();" in guard
    assert "voice-conversation-mode" in guard
    assert "Conversar agora" in guard
    assert "hasNativeSpeechRecognition" in guard
    assert "127.0.0.1" in guard
    assert "mobileAudioInput" not in guard
    assert "captureUnavailable = 'insecure-http'" not in guard


def test_insecure_lan_guard_clears_stale_active_state_when_voice_stops():
    guard = read("app/static/voice-insecure-lan-guard.js")

    assert "const resetConversationMode = () => {" in guard
    assert "card.hidden = true;" in guard
    assert "voz desligada" in guard
    assert "conversa por voz foi desligada" in guard
    assert "modal.addEventListener('close', resetConversationMode);" in guard
    assert "ensureConversationModeCard();\n      resetConversationMode();" in guard
