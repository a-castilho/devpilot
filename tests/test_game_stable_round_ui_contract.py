from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE = ROOT / "app/static/game/stable-round-ui.js"
RECOVERY = ROOT / "app/static/game/recovery-runtime.js"
KEEPER = ROOT / "app/static/game/flow-keeper.js"
RUNTIME_SYNC = ROOT / "app/static/game/runtime-state-sync.js"
BOOT = ROOT / "app/static/game/game-bootstrap.js"
INDEX = ROOT / "app/static/game/index.html"


def test_active_round_surface_lives_outside_polling_target():
    source = STABLE.read_text(encoding="utf-8")
    assert "devpilot-game-stable-round-v91" in source
    assert "document.querySelector('.devpilot-game-stage')" in source
    assert "target.style.setProperty('display', detailsOpen ? 'block' : 'none', 'important')" in source
    assert "if (nextSignature === lastSignature) return true" in source


def test_failure_surface_reports_exact_position_reason_and_outcome():
    source = STABLE.read_text(encoding="utf-8")
    assert "Diagnóstico da falha" in source
    assert "data-game-recovery-position" in source
    assert "data-game-recovery-reason" in source
    assert "data-game-recovery-code" in source
    assert "data-game-recovery-state" in source
    assert "recoverableFailure" in source
    assert "['failed', 'blocked']" in source
    assert "failure?.message" in source
    assert "failure?.code" in source
    for state in ("awaiting_intervention", "intervention_required", "recovery_exhausted"):
        assert state in source
    assert "O DevPilot não vai inventar credencial, permissão ou decisão humana." in source


def test_retesting_uses_canonical_backend_status_instead_of_stale_snapshot():
    source = STABLE.read_text(encoding="utf-8")
    assert "recovery?.task_status || state?.taskStatus" in source
    assert "recoverableFailure(state, recovery)" in source
    assert "recoveryState === 'retesting'" in source
    assert "Correção/reteste em andamento" in source
    assert "recovery?.task_status" in source


def test_recovery_has_one_backend_owner_and_bounded_observer():
    recovery = RECOVERY.read_text(encoding="utf-8")
    keeper = KEEPER.read_text(encoding="utf-8")
    assert "Backend/worker is the only recovery owner" in recovery
    assert "__devpilotGameRecoveryForTask" in recovery
    assert "__devpilotGameRefreshRecovery" in recovery
    assert "can_resume_original" in recovery
    assert "request(taskId, 'resume')" in recovery
    assert "agent_recovery is deliberately not polled here" in recovery
    assert "RECOVERY_RECHECK_MS = 30000" in keeper
    assert "FAILED_POLL_MS = 8000" in keeper
    assert "TERMINAL_RECOVERY_STATES" in keeper
    assert "OBSERVED_FAILURE_STATUSES" in keeper
    assert "shouldWatchFailure" in keeper
    assert "shouldKeepMoving" not in keeper


def test_internal_recovery_task_never_becomes_game_phase():
    source = RUNTIME_SYNC.read_text(encoding="utf-8")
    assert "[DEVPILOT_FAILURE_RECOVERY_V1]" in source
    assert "failure-recovery" in source
    assert ".filter(task => !isFailureRecoveryTask(task))" in source
    assert "mistake a recovery task for a newer phase task" in source


def test_bootstrap_loads_stable_ui_and_uses_one_revision():
    boot = BOOT.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")
    assert "game/stable-round-ui.js" in boot
    assert "game-flow-v91-20260903" in boot
    assert "game-flow-v91-20260903" in html
    assert "unified-v91" in boot


def run_contract():
    test_active_round_surface_lives_outside_polling_target()
    test_failure_surface_reports_exact_position_reason_and_outcome()
    test_retesting_uses_canonical_backend_status_instead_of_stale_snapshot()
    test_recovery_has_one_backend_owner_and_bounded_observer()
    test_internal_recovery_task_never_becomes_game_phase()
    test_bootstrap_loads_stable_ui_and_uses_one_revision()
    print("GAME_STABLE_ROUND_UI=OK")


if __name__ == "__main__":
    run_contract()
