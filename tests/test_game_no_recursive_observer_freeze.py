from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
GATE = (ROOT / "app/static/game/delivery-gate.js").read_text(encoding="utf-8")
BUILD = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")


def test_objective_controls_use_explicit_events_without_mutation_observer():
    assert "MutationObserver" not in OBJECTIVE
    assert "devpilot:game:rendered" in OBJECTIVE
    assert "devpilot:game:state" in OBJECTIVE
    assert "if (scheduled) return;" in OBJECTIVE


def test_legacy_action_runtime_cannot_reintroduce_recursive_replay_loop():
    assert "while (loadRequested)" not in ACTION
    assert "loadRequested = true" not in ACTION
    assert "do {" not in ACTION
    assert "'game/action-runtime.js'" not in BOOT


def test_delivery_gate_never_wraps_main_loader():
    assert "window.loadBuildGame = async" not in GATE
    assert "__devpilotDeliveryGateDoesNotWrapLoader = true" in GATE
    assert "MAX_PHASES = 7" in GATE
    assert "TASK_LIMIT = 24" in GATE
    assert "limit=${TASK_LIMIT}" in GATE


def test_enhancements_start_only_after_core_and_yield_between_modules():
    core = BOOT.index("await withTimeout(window.loadBuildGame()")
    ready = BOOT.index("window.__devpilotGameCoreReady = true")
    enhancements = BOOT.index("startEnhancements();")
    assert core < ready < enhancements
    assert "await new Promise(resolve => window.setTimeout(resolve, 0));" in BOOT
    assert BOOT.index("game/task-payload-guard.js") < BOOT.index("game/delivery-gate.js")


def test_controller_has_one_guarded_automatic_refresh_loop():
    assert "let controllerBusy = false;" in BUILD
    assert "if (controllerBusy) return snapshot();" in BUILD
    assert "window.clearTimeout(controllerTimer);" in BUILD
    assert "controllerTimer = window.setTimeout" in BUILD


def test_android_cache_revision_is_v73():
    revision = "game-unified-v73-20260902"
    assert revision in BOOT
    assert INDEX.count(revision) >= 5
