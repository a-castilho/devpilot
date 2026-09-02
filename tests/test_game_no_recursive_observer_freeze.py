from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = (ROOT / "app/static/game/start-round-mobile.js").read_text(encoding="utf-8")
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
GATE = (ROOT / "app/static/game/delivery-gate.js").read_text(encoding="utf-8")


def test_start_round_uses_explicit_render_events_without_mutation_observer():
    assert "MutationObserver" not in START
    assert "devpilot:game:rendered" in START
    assert "if (scheduled) return;" in START


def test_objective_controls_use_explicit_render_events_without_mutation_observer():
    assert "MutationObserver" not in OBJECTIVE
    assert "devpilot:game:rendered" in OBJECTIVE
    assert "devpilot-game-quick-start" in OBJECTIVE


def test_action_runtime_coalesces_refreshes_without_recursive_replay_loop():
    assert "window.__devpilotBaseLoadBuildGame = baseLoad" in ACTION
    assert "if (loadInFlight)" in ACTION
    assert "return loadInFlight;" in ACTION
    assert "while (loadRequested)" not in ACTION
    assert "do {" not in ACTION
    assert "devpilot:game:rendered" in ACTION


def test_delivery_gate_never_wraps_main_loader():
    assert "window.loadBuildGame = async" not in GATE
    assert "__devpilotDeliveryGateDoesNotWrapLoader = true" in GATE
    assert "MAX_PHASES = 7" in GATE
    assert "TASK_LIMIT = 24" in GATE


def test_optional_enhancements_only_start_after_core_render_and_yield_between_modules():
    core = BOOT.index("await withTimeout(window.loadBuildGame()")
    ready = BOOT.index("window.__devpilotGameCoreReady = true")
    enhancements = BOOT.index("startEnhancementsAfterPaint();")
    assert core < ready < enhancements
    assert "await yieldToBrowser();" in BOOT
    assert BOOT.index("game/action-runtime.js") < BOOT.index("game/delivery-gate.js")


def test_android_cache_revision_changes_with_v64_entry_fix():
    revision = "release-1.2.0-game-entry-stable-v64-20260902"
    assert revision in BOOT
    assert INDEX.count(revision) == 5
