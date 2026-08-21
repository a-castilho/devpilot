from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_insecure_lan_guard_preserves_voice_fallback_and_offers_loopback():
    guard = read("app/static/voice-insecure-lan-guard.js")

    assert "return originalStart.call(startButton, event);" in guard
    assert "preventDefault" not in guard
    assert "stopPropagation" not in guard
    assert "voice-open-loopback" in guard
    assert "127.0.0.1" in guard
    assert "insecure-lan-fallback" in guard
    assert "captureUnavailable = 'insecure-http'" not in guard
