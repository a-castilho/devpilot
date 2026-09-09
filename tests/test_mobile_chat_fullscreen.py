from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_mobile_chat_uses_full_dynamic_viewport():
    css = read("app/static/voice-mobile-fix.css")

    assert "height: 100dvh !important;" in css
    assert "min-height: 100dvh !important;" in css
    assert "inset: 0 !important;" in css
    assert "overflow: hidden !important;" in css


def test_mobile_conversation_grows_and_scrolls_inside_viewport():
    css = read("app/static/voice-mobile-fix.css")

    assert "flex: 1 1 0 !important;" in css
    assert "max-height: none !important;" in css
    assert "overflow-y: auto !important;" in css
    assert "-webkit-overflow-scrolling: touch;" in css


def test_mobile_composer_remains_in_layout_at_bottom():
    css = read("app/static/voice-mobile-fix.css")

    assert "flex: 0 0 auto !important;" in css
    assert "bottom: calc(74px + env(safe-area-inset-bottom)) !important;" in css
