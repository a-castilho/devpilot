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
    assert "devpilot:game:rendered" in GATE


def test_task_creation_is_post_first_and_recovery_is_bounded():
    post = GUARD.index("const result = await originalApi(path, options);")
    recover = GUARD.index("const recovered = await recover(identity);")
    assert post < recover
    assert "timeoutMs:3500" in GUARD
    assert "retry:false" in GUARD
    assert "findGameCreations" not in GUARD


def test_game_trace_memory_is_bounded():
    assert "rows.length > 48" in GUARD
    assert "rows.splice(0, rows.length - 48)" in GUARD
    assert "devpilot-game-debug" in GUARD


def test_legacy_action_runtime_cannot_block_current_game_startup():
    assert "'game/action-runtime.js'" not in BOOT
    assert "while (loadRequested)" not in ACTION
    assert "loadRequested = true" not in ACTION


def test_boot_loads_current_guard_ui_and_gate_after_real_core():
    assert "await withTimeout(window.loadBuildGame()" in BOOT
    assert "window.__devpilotGameCoreReady = true" in BOOT
    assert "startEnhancements();" in BOOT
    assert BOOT.index("'game/task-payload-guard.js'") < BOOT.index("'game/objective-controls.js'")
    assert BOOT.index("'game/objective-controls.js'") < BOOT.index("'game/delivery-gate.js'")
