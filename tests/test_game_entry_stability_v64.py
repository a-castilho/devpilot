from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
GATE = (ROOT / "app/static/game/delivery-gate.js").read_text(encoding="utf-8")
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")
START = (ROOT / "app/static/game/start-round-mobile.js").read_text(encoding="utf-8")
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")

REVISION = "release-1.2.0-game-entry-stable-v64-20260902"


def test_entry_has_exactly_three_critical_scripts_and_core_first_boot():
    assert INDEX.count('<script src="/assets/') == 3
    assert INDEX.count(REVISION) == 5
    core = BOOT.index("await withTimeout(window.loadBuildGame()")
    ready = BOOT.index("window.__devpilotGameCoreReady = true")
    enhancements = BOOT.index("startEnhancementsAfterPaint();")
    assert core < ready < enhancements


def test_action_runtime_is_the_only_optional_loader_wrapper():
    assert "window.loadBuildGame = async" in ACTION
    assert "window.loadBuildGame = async" not in GATE
    assert "const originalLoad = window.loadBuildGame" not in GATE
    assert "__devpilotDeliveryGateDoesNotWrapLoader = true" in GATE
    assert "while (loadRequested)" not in ACTION
    assert "do {" not in ACTION


def test_standalone_controls_cannot_return_to_mutation_observers():
    assert "MutationObserver" not in OBJECTIVE
    assert "MutationObserver" not in START
    assert "devpilot:game:rendered" in OBJECTIVE
    assert "devpilot:game:rendered" in START


def test_gate_is_background_lightweight_and_matches_seven_phase_pipeline():
    assert "MAX_PHASES = 7" in GATE
    assert "TASK_LIMIT = 24" in GATE
    assert "devpilot:game:rendered" in GATE
    assert "timeoutMs: 3500" in GATE
    assert "retry: false" in GATE


def test_v63_fast_creation_remains_preserved_under_v64_entry_fix():
    assert "window.__devpilotGameNoPreflightV63 = true" in GUARD
    assert "const result = await originalApi(path, options);" in GUARD
    assert "const previous = await findGameCreations(options);" not in GUARD
    assert "mobileRuntime ? 90 : 45" in BOOT
