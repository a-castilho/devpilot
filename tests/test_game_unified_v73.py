from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app/static/game/index.html"
BOOT = ROOT / "app/static/game/game-bootstrap.js"
ENGINE = ROOT / "app/static/build-game.js"
UI = ROOT / "app/static/game/objective-controls.js"
GUARD = ROOT / "app/static/game/task-payload-guard.js"
GATE = ROOT / "app/static/game/delivery-gate.js"
KEEPER = ROOT / "app/static/game/flow-keeper.js"
SERVER = ROOT / "app/game_round_orchestrator.py"
WORKER = ROOT / "app/worker_entry.py"
EMBEDDED = ROOT / "app/embedded_worker.py"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_entry_has_one_controller_and_visible_v81_fallback():
    source = text(INDEX)
    assert "game-data-v81-20260903" in source
    assert 'data-devpilot-game-version="v81"' in source
    assert "data-game-critical-boot-v81" in source
    assert 'data-game-boot-state="loading"' in source
    assert "/assets/game/standalone.css" in source
    assert "/assets/styles.css" not in source


def test_boot_makes_server_pipeline_authoritative():
    source = text(BOOT)
    entry = source.split("const ENTRY_ASSETS = [", 1)[1].split("];", 1)[0]
    assert "task-payload-guard.js" in entry
    assert "objective-controls.js" in entry
    assert "project-switch-approval.js" in entry
    assert "flow-keeper.js" in entry
    assert "delivery-gate.js" not in entry
    assert "recovery-runtime.js" not in entry
    assert "action-runtime.js" not in entry
    assert "game-data-v81-20260903" in source
    assert "server-orchestrated-v81" in source


def test_engine_exposes_direct_one_click_controller():
    source = text(ENGINE)
    assert "window.__devpilotGameControllerV73" in source
    assert "const startRound = async" in source
    assert "await createPhaseTask(1, targetGoal" in source
    assert "const refreshAndAdvance = async" in source
    assert "throw failure" in source


def test_phase_only_passes_after_independent_verifier():
    source = text(ENGINE)
    assert "const isVerifierTask" in source
    assert "isVerifierTask(task) && normalize(task.status) === 'completed'" in source
    assert "const isAwaitingGate" in source


def test_simple_ui_calls_controller_not_hidden_buttons():
    source = text(UI)
    assert "__devpilotGameUiV73Ready" in source
    assert "await engine.startRound({projectId, goal: targetGoal})" in source
    assert "Jogar agora" in source
    assert "Trabalhando automaticamente" in source
    assert "Depois do clique você fica nesta tela" in source
    assert "DRAFT_GOAL_KEY" in source
    assert "phaseButton.click" not in source
    assert "data-play-phase" not in source


def test_flow_keeper_is_passive_compact_observer():
    source = text(KEEPER)
    assert "__devpilotGameFlowKeeperV81Ready" in source
    assert "/ui/game-tasks?project_id=" in source
    assert "state.missionId" in source
    assert "state.goal" in source
    assert "await window.loadBuildGame()" in source
    assert "engine.refresh()" not in source
    assert "__devpilotEnsureDeliveryGate" not in source
    assert ".retry(" not in source
    assert "visibilitychange" in source


def test_server_orchestrator_owns_gate_next_phase_and_bounded_retry():
    source = text(SERVER)
    assert "class GameRoundOrchestrator" in source
    assert "[DEVPILOT_GAME_SERVER_ORCHESTRATED_V1]" in source
    assert "groups[(project_id, mission)]" in source
    assert "[Jogo] Gate {phase}" in source
    assert "[Jogo] Etapa {phase}" in source
    assert "MAX_AUTOMATIC_RETRIES = 3" in source
    assert "Use esta resposta para corrigir a nova tentativa" in source
    assert "STALE_QUEUE_MINUTES = 5" in source


def test_both_worker_modes_run_server_game_orchestrator():
    assert "game.tick()" in text(WORKER)
    assert "self._game.tick()" in text(EMBEDDED)


def test_guard_is_bounded_and_blocks_duplicate_creation():
    source = text(GUARD)
    assert "rows.length > 48" in source
    assert "requestPath !== '/tasks' || method !== 'POST'" in source
    assert "game-create:dedupe" in source
    assert "const recentCreations = new Map();" in source
    assert "window.__devpilotGameCreateSequentialDedup = true" in source


def test_legacy_gate_remains_for_compatibility_but_is_not_booted():
    source = text(GATE)
    assert "window.__devpilotEnsureDeliveryGate = ensureVerifier" in source
    assert "retryFailed = false" in source
