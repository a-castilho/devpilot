from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "app/static/game-workflow-adapter.js"
FEATURE_LOADER = ROOT / "app/static/feature-loader.js"


def test_game_workflow_reuses_existing_task_run_apis():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "/api/task-runs/latest?limit=500" in source
    assert "/api/task-runs/${encodeURIComponent(summary.run_id)}" in source
    assert "/api/tasks/${encodeURIComponent(taskId)}/retry" in source
    assert "/api/game/" not in source


def test_game_workflow_preserves_authorization_shield():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "SHIELD_BLOCKED" in source
    assert "before.requires_authorization" in source
    assert "fluxo normal de autorização" in source


def test_game_workflow_adapter_is_lazy_loaded_with_game_bundle():
    source = FEATURE_LOADER.read_text(encoding="utf-8")
    game_bundle = source.split("game: [", 1)[1].split("],", 1)[0]

    assert "'game-workflow-adapter.js'" in game_bundle
    assert game_bundle.index("'game-workflow-adapter.js'") < game_bundle.index("'build-game.js'")


def test_game_state_is_derived_from_real_run_modes():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "mode.includes('analysis')" in source
    assert "mode === 'execute'" in source
    assert "mode === 'budget-blocked'" in source
    assert "status === 'completed'" in source
    assert "status === 'failed'" in source
