from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "static" / "viewport-adaptive-v15.js"


def source() -> str:
    return SOURCE.read_text(encoding="utf-8")


def test_mobile_scroll_does_not_recalculate_global_viewport_layout():
    js = source()
    assert "visualViewport?.addEventListener('scroll'" not in js
    assert "scheduleViewportResize" in js
    assert "Math.abs(width - lastObservedWidth) < 2" in js


def test_viewport_updates_are_idempotent():
    js = source()
    assert "let lastSignature = ''" in js
    assert "if (signature === lastSignature) return" in js
    assert "root.style.getPropertyValue(name) === value" in js
    assert "root.dataset[name] === value" in js


def test_mobile_signature_ignores_browser_chrome_height_changes():
    js = source()
    assert "const mobile = width <= 900" in js
    assert "? [width, mode, value.zoomedOut, value.compact, boost3].join('|')" in js
    assert "Viewport Adaptive V38 sem reflow durante scroll mobile" in js
