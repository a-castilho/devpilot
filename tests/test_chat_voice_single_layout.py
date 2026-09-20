from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WATCHDOG = ROOT / "app" / "static" / "chat-request-watchdog.js"


def test_voice_chat_uses_one_canonical_conversation_surface():
    source = WATCHDOG.read_text(encoding="utf-8")

    assert "#voice-visible-conversation" in source
    assert "#voice-chat-log, #voice-chat-preview" in source
    assert "conversations.slice(1).forEach(node => node.remove())" in source
    assert "panel.dataset.singleChatLayout = '1'" in source


def test_single_chat_cleanup_does_not_replace_voice_runtime_handlers():
    source = WATCHDOG.read_text(encoding="utf-8")

    assert "stopImmediatePropagation" not in source
    assert "getUserMedia" not in source
    assert "MediaRecorder" not in source
    assert "SpeechRecognition" not in source


def test_chat_watchdog_remains_active_after_layout_consolidation():
    source = WATCHDOG.read_text(encoding="utf-8")

    assert "CHAT_REQUEST_TIMEOUT_MS = 45000" in source
    assert "requestPath(input) !== '/api/chat'" in source
    assert "TimeoutError" in source
