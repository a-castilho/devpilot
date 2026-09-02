from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
GATE = (ROOT / "app/static/game/delivery-gate.js").read_text(encoding="utf-8")
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")


def test_delivery_gate_never_wraps_main_game_loader():
    assert "MAX_PHASES = 7" in GATE
    assert "TASK_LIMIT = 24" in GATE
    assert "window.loadBuildGame = async" not in GATE
    assert "__devpilotDeliveryGateDoesNotWrapLoader = true" in GATE
    assert "setTimeout(scheduleGate" in GATE


def test_task_creation_precheck_is_bounded_and_nonfatal():
    assert "PRECHECK_TIMEOUT_MS = 1400" in GUARD
    assert "CREATE_TIMEOUT_MS = 6500" in GUARD
    assert "RECOVERY_TIMEOUT_MS = 2200" in GUARD
    assert "game-create:dedupe:precheck-timeout" in GUARD
    assert "const result = await originalApi(path" in GUARD


def test_game_trace_memory_is_bounded():
    assert "TRACE_LIMIT = 80" in GUARD
    assert "window.__devpilotGameBootTrace.splice" in GUARD
    assert "console.debug('[DevPilot Game Trace]'" not in GUARD


def test_action_runtime_blocks_fast_duplicate_taps():
    assert "now - previous < 650" in ACTION
    assert "event.stopImmediatePropagation()" in ACTION
    assert "__devpilotGameRunAction" in ACTION


def test_boot_loads_coordinator_and_guard_before_ui_enhancements():
    assert BOOT.index("game/action-runtime.js") < BOOT.index("game/task-payload-guard.js")
    assert BOOT.index("game/task-payload-guard.js") < BOOT.index("game/objective-controls.js")
    assert BOOT.index("game/objective-controls.js") < BOOT.index("game/delivery-gate.js")
