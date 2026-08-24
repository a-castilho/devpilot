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
    assert "modal.addEventListener('close', resetConversationMode);" in guard
    assert "ensureConversationModeCard();\n      resetConversationMode();" in guard


def test_insecure_lan_guard_uses_real_microphone_state_instead_of_status_text_only():
    guard = read("app/static/voice-insecure-lan-guard.js")

    assert "const isVoiceSessionActive = () => Boolean(" in guard
    assert "startButton.getAttribute('aria-pressed') === 'true'" in guard
    assert "voice-session-active" in guard
    assert "const syncConversationModeState = () => {" in guard
    assert "if (!active) {" in guard
    assert "const voiceStateObserver = new MutationObserver(syncConversationModeState);" in guard
    assert "attributeFilter: ['aria-pressed']" in guard
    assert "attributeFilter: ['class']" in guard


def test_switching_to_text_stops_an_active_microphone_session():
    guard = read("app/static/voice-insecure-lan-guard.js")

    assert "typeof window.devpilotVoiceStop === 'function'" in guard
    assert "window.devpilotVoiceStop('Modo texto ativo. Digite sua mensagem para o DevPilot.');" in guard
