from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
GATE = (ROOT / "app/static/game/delivery-gate.js").read_text(encoding="utf-8")
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")

REVISION = "game-unified-v73-20260902"


def test_entry_has_exactly_three_critical_scripts_and_core_first_boot():
    assert INDEX.count('<script src="/assets/') == 3
    assert INDEX.count(REVISION) >= 5
    core = BOOT.index("await withTimeout(window.loadBuildGame()")
    ready = BOOT.index("window.__devpilotGameCoreReady = true")
    enhancements = BOOT.index("startEnhancements();")
    assert core < ready < enhancements


def test_game_startup_has_single_loader_owner():
    assert "'game/action-runtime.js'" not in BOOT
    assert "window.loadBuildGame = async" not in GATE
    assert "const originalLoad = window.loadBuildGame" not in GATE
    assert "__devpilotDeliveryGateDoesNotWrapLoader = true" in GATE
    assert "while (loadRequested)" not in ACTION


def test_standalone_controls_are_event_driven_not_mutation_observer_driven():
    assert "MutationObserver" not in OBJECTIVE
    assert "devpilot:game:state" in OBJECTIVE
    assert "devpilot:game:rendered" in OBJECTIVE


def test_gate_is_lightweight_and_matches_seven_phase_pipeline():
    assert "MAX_PHASES = 7" in GATE
    assert "limit=24" in GATE
    assert "devpilot:game:rendered" in GATE
    assert "timeoutMs:4000" in GATE
    assert "retry:false" in GATE


def test_fast_creation_is_post_first_with_only_error_recovery():
    post = GUARD.index("const result = await originalApi(path, options);")
    recover = GUARD.index("const recovered = await recover(identity);")
    assert post < recover
    assert "findGameCreations" not in GUARD
    assert "window.__devpilotGameCreateDedup = true" in GUARD
    assert "window.__devpilotGameCreateRecovery = true" in GUARD
