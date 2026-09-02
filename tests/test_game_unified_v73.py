from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app/static/game/index.html"
BOOT = ROOT / "app/static/game/game-bootstrap.js"
ENGINE = ROOT / "app/static/build-game.js"
UI = ROOT / "app/static/game/objective-controls.js"
GUARD = ROOT / "app/static/game/task-payload-guard.js"
GATE = ROOT / "app/static/game/delivery-gate.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_entry_has_one_controller_and_no_v67_bridge():
    source = text(INDEX)
    assert "game-unified-v73-20260902" in source
    assert "data-game-nonblocking-entry-v67" not in source
    assert "/assets/game/standalone.css" in source
    assert "/assets/styles.css" not in source


def test_boot_does_not_load_action_runtime_wrapper():
    source = text(BOOT)
    entry = source.split("const ENTRY_ASSETS = [", 1)[1].split("];", 1)[0]
    assert "task-payload-guard.js" in entry
    assert "objective-controls.js" in entry
    assert "delivery-gate.js" in entry
    assert "action-runtime.js" not in entry
    assert "unified-v73" in source


def test_engine_exposes_direct_one_click_controller():
    source = text(ENGINE)
    assert "window.__devpilotGameControllerV73" in source
    assert "const startRound = async" in source
    assert "await createPhaseTask(1, targetGoal" in source
    assert "const refreshAndAdvance = async" in source
    assert "window.__devpilotEnsureDeliveryGate" in source
    assert "throw failure" in source


def test_phase_only_passes_after_independent_verifier():
    source = text(ENGINE)
    assert "const isVerifierTask" in source
    assert "isVerifierTask(task) && normalize(task.status) === 'completed'" in source
    assert "const isAwaitingGate" in source


def test_simple_ui_calls_controller_not_hidden_buttons():
    source = text(UI)
    assert "__devpilotGameUiV73Ready" in source
    assert "await engine.startRound({projectId, goal})" in source
    assert "Jogar agora" in source
    assert "Rodada automática" in source
    assert "phaseButton.click" not in source
    assert "data-play-phase" not in source


def test_guard_is_bounded_and_only_wraps_task_creation():
    source = text(GUARD)
    assert "rows.length > 48" in source
    assert "requestPath !== '/tasks' || method !== 'POST'" in source
    assert "game-create:dedupe" in source


def test_gate_allows_explicit_retry_of_failed_verifier():
    source = text(GATE)
    assert "retryFailed = false" in source
    assert "retryFailed && FAILED.has(status)" in source
    assert "window.__devpilotEnsureDeliveryGate = ensureVerifier" in source
