from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "app/static/game/runtime-state-sync.js"
RECOVERY = ROOT / "app/static/game/recovery-runtime.js"
INDEX = ROOT / "app/static/game/index.html"


def test_game_uses_orchestrator_runtime_as_source_of_truth():
    source = SYNC.read_text(encoding="utf-8")
    assert "/tasks/orchestrator/runtime" in source
    assert "orchestrator_state" in source
    assert "raw_status" in source
    assert "runtimeState === 'archived'" in source
    assert "copy.status = 'canceled'" in source
    assert "RUNTIME_CACHE_MS = 15000" in source


def test_archived_game_task_gets_one_controller_replacement():
    source = RECOVERY.read_text(encoding="utf-8")
    assert "orchestratorState" in source
    assert "runtimeState === 'archived'" in source
    assert "return originalRetry();" in source
    assert "inFlight" in source
    assert "POLL_MS = 3500" not in source


def test_sync_loads_before_build_game_controller():
    html = INDEX.read_text(encoding="utf-8")
    assert "game-flow-v88-20260903" in html
    assert "/assets/game/runtime-state-sync.js" in html
    assert html.index("runtime-state-sync.js") < html.index("build-game.js")


def run_contract():
    test_game_uses_orchestrator_runtime_as_source_of_truth()
    test_archived_game_task_gets_one_controller_replacement()
    test_sync_loads_before_build_game_controller()
    print("GAME_RUNTIME_STATE_SYNC_V88=OK")


if __name__ == "__main__":
    run_contract()
