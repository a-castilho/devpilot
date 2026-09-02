from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = (ROOT / "app/static/game/start-round-mobile.js").read_text(encoding="utf-8")
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_start_round_does_not_observe_the_whole_document_tree():
    assert "observer.observe(document.documentElement" not in START
    assert "viewObserver.observe(view, {childList:true});" in START
    assert "subtree:true" not in START


def test_start_round_decorator_is_idempotent_before_touching_text():
    assert "const desiredText" in START
    assert "if (button.textContent !== desiredText) button.textContent = desiredText;" in START
    assert "if (scheduled) return;" in START


def test_objective_controls_do_not_observe_the_whole_document_tree():
    assert "observer.observe(document.documentElement" not in OBJECTIVE
    assert "viewObserver.observe(view, {childList:true});" in OBJECTIVE
    assert "subtree: true" not in OBJECTIVE
    assert "subtree:true" not in OBJECTIVE


def test_optional_enhancements_yield_to_browser_between_modules():
    assert "const yieldToBrowser" in BOOT
    assert "await yieldToBrowser();" in BOOT


def test_android_cache_revision_changes_with_observer_fix():
    revision = "release-1.2.0-game-core-20260902-4"
    assert revision in BOOT
    assert revision in INDEX
