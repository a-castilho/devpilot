from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = (ROOT / "app/static/game/start-round-mobile.js").read_text(encoding="utf-8")
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")


def test_start_round_uses_render_events_without_mutation_observer():
    assert "MutationObserver" not in START
    assert "devpilot:game:rendered" in START
    assert "subtree:true" not in START


def test_start_round_decorator_is_idempotent_before_touching_text():
    assert "const desiredText" in START
    assert "if (button.textContent !== desiredText)" in START
    assert "button.textContent = initial ? 'Iniciar jogo' : 'Nova rodada'" in START
    assert "if (scheduled) return;" in START


def test_objective_controls_use_render_events_without_mutation_observer():
    assert "MutationObserver" not in OBJECTIVE
    assert "devpilot:game:rendered" in OBJECTIVE
    assert "subtree: true" not in OBJECTIVE
    assert "subtree:true" not in OBJECTIVE


def test_action_runtime_is_single_loader_coordinator():
    assert "window.__devpilotBaseLoadBuildGame = baseLoad" in ACTION
    assert "if (loadInFlight)" in ACTION
    assert "loadRequested = true" in ACTION
    assert "devpilot:game:rendered" in ACTION


def test_optional_enhancements_yield_to_browser_between_modules():
    assert "const yieldToBrowser" in BOOT
    assert "await yieldToBrowser();" in BOOT
    assert BOOT.index("game/action-runtime.js") < BOOT.index("game/objective-controls.js")


def test_android_cache_revision_changes_with_navigation_fix():
    revision = "release-1.2.0-game-simple-v56-20260902"
    assert revision in BOOT
    assert revision in INDEX
