from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FALLBACK = (ROOT / "app/static/voice-insecure-lan-recorder-fallback.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_mobile_http_voice_loads_system_recorder_fallback_after_guard():
    voice_bundle = LOADER.split("voice: [", 1)[1].split("],", 1)[0]
    assert "voice-insecure-lan-guard.js" in voice_bundle
    assert "voice-insecure-lan-recorder-fallback.js" in voice_bundle
    assert voice_bundle.index("voice-insecure-lan-guard.js") < voice_bundle.index("voice-insecure-lan-recorder-fallback.js")


def test_mobile_http_voice_uses_audio_capture_without_get_user_media():
    assert "!window.isSecureContext" in FALLBACK
    assert "audioInput.type = 'file'" in FALLBACK
    assert "audioInput.accept = 'audio/*" in FALLBACK
    assert "audioInput.setAttribute('capture', '')" in FALLBACK
    assert "event.stopImmediatePropagation()" in FALLBACK
    assert "audioInput.click()" in FALLBACK
    assert "getUserMedia" not in FALLBACK


def test_recorded_audio_is_transcribed_by_existing_backend_route():
    assert "api('/voice/transcriptions'" in FALLBACK
    assert "form.append('audio'" in FALLBACK
    assert "transcriptInput.value = text" in FALLBACK
    assert "transcriptInput.dispatchEvent(new Event('input', {bubbles: true}))" in FALLBACK
