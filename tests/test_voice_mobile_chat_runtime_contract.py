from pathlib import Path


VOICE_PERMISSION = Path("app/static/voice-microphone-permission.js")


def test_mobile_voice_capture_requests_microphone_recorder():
    source = VOICE_PERMISSION.read_text(encoding="utf-8")
    assert "setAttribute('capture', 'microphone')" in source


def test_transcription_ready_submits_to_ai_conversation():
    source = VOICE_PERMISSION.read_text(encoding="utf-8")
    assert "window.devpilotVoiceConversationSubmit" in source
    assert "value.startsWith('transcrição pronta')" in source
    assert "submitConversationWhenReady()" in source
