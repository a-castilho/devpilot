from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_repeatai_uses_compiled_iframe_and_releases_it_after_navigation():
    source = (STATIC_DIR / "example-project.js").read_text(encoding="utf-8")

    assert "const target = FALLBACK_URL;" in source
    assert "frame.src = 'about:blank';" in source
    assert "releaseRepetAI();" in source


def test_repeatai_stops_global_observing_and_bounds_capture_memory():
    training = (STATIC_DIR / "example-project-mobile-training.js").read_text(encoding="utf-8")
    frame = (STATIC_DIR / "examples" / "repeatai" / "index.html").read_text(encoding="utf-8")

    assert "if (scan()) rootObserver.disconnect();" in training
    assert "characterData: true" not in training
    assert "const MAX_EVENTS = 1200;" in frame
    assert "state.events.splice(0,state.events.length-MAX_EVENTS);" in frame
    assert "now-state.lastMouseSample<250" in frame
