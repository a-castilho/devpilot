from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = (ROOT / "app/static/game/flow-keeper.js").read_text(encoding="utf-8")
RECOVERY = (ROOT / "app/static/game/recovery-runtime.js").read_text(encoding="utf-8")
SYNC = (ROOT / "app/static/game/runtime-state-sync.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_failed_state_has_bounded_polling_budget():
    assert "FIRST_FAILURE_DELAY_MS = 250" in FLOW
    assert "FAILED_POLL_MS = 8000" in FLOW
    assert "HIDDEN_FAILED_POLL_MS = 20000" in FLOW
    assert "RECOVERY_RECHECK_MS = 30000" in FLOW
    assert "if (!engine || !shouldWatchFailure(state))" in FLOW
    assert "recoveryChecks" in FLOW


def test_healthy_round_has_no_second_flow_keeper_poll_loop():
    assert "state.failed && !state.done" in FLOW
    assert "Healthy rounds are already refreshed by build-game.js" in FLOW
    assert "VISIBLE_DELAY_MS = 2500" not in FLOW


def test_recovery_runtime_does_not_self_poll():
    assert "window.__devpilotGameRecoveryV88Ready" in RECOVERY
    assert "POLL_MS = 3500" not in RECOVERY
    assert "setTimeout(async () =>" not in RECOVERY
    assert "flow-keeper observes the task with a bounded cadence" in RECOVERY
    assert "orchestratorState" in RECOVERY


def test_runtime_snapshot_is_cached_between_game_polls():
    assert "RUNTIME_CACHE_MS = 15000" in SYNC
    assert "now() - runtimeCache.at < RUNTIME_CACHE_MS" in SYNC
    assert "window.__devpilotGameRuntimeStateSyncV88Ready" in SYNC


def test_v88_cache_bust_is_consistent():
    assert "game-flow-v88-20260903" in INDEX
    assert 'data-devpilot-game-version="v88"' in INDEX
    assert "const ASSET_REVISION = 'game-flow-v88-20260903'" in BOOT
    assert "unified-v88" in BOOT


def run_contract():
    test_failed_state_has_bounded_polling_budget()
    test_healthy_round_has_no_second_flow_keeper_poll_loop()
    test_recovery_runtime_does_not_self_poll()
    test_runtime_snapshot_is_cached_between_game_polls()
    test_v88_cache_bust_is_consistent()
    print("GAME_REQUEST_BUDGET_V88=OK")


if __name__ == "__main__":
    run_contract()
