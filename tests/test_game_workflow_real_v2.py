from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "app" / "static" / "game-workflow-adapter.js"
BRIDGE = ROOT / "app" / "static" / "game-workflow-ui.js"
LOADER = ROOT / "app" / "static" / "feature-loader.js"


def test_game_bundle_loads_real_workflow_before_visual_modules():
    source = LOADER.read_text(encoding="utf-8")
    bundle = source.split("game: [", 1)[1].split("],", 1)[0]

    assert "'game-workflow-adapter.js'" in bundle
    assert "'game-workflow-ui.js'" in bundle
    assert bundle.index("'game-workflow-adapter.js'") < bundle.index("'build-game.js'")
    assert bundle.index("'game-workflow-ui.js'") > bundle.index("'build-game-weapons.js'")


def test_adapter_uses_existing_task_and_run_apis_only():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "/api/task-runs/latest?limit=500" in source
    assert "/api/task-runs/${encodeURIComponent(summary.run_id)}" in source
    assert "/api/tasks/${encodeURIComponent(taskId)}/retry" in source
    assert "/api/game/" not in source


def test_authorization_is_a_shield_and_cannot_be_retried():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "status === 'blocked' || status === 'awaiting_approval'" in source
    assert "SHIELD_BLOCKED" in source
    assert "before.requires_authorization" in source
    assert "fluxo normal de autorização" in source
    assert "Retry só é permitido para missão realmente falha" in source


def test_game_state_comes_from_real_task_run_state():
    source = ADAPTER.read_text(encoding="utf-8")

    assert "mode.includes('analysis')" in source
    assert "mode === 'execute'" in source
    assert "mode === 'budget-blocked'" in source
    assert "status === 'completed'" in source
    assert "status === 'failed' || status === 'cancelled'" in source
    assert "devpilot:game-state" in source
    assert "devpilot:game-error" in source


def test_ui_reconciles_from_backend_instead_of_window_state_or_local_success():
    source = BRIDGE.read_text(encoding="utf-8")

    assert "/api/tasks?project_id=${encodeURIComponent(projectId)}&limit=500" in source
    assert "window.DevPilotGameWorkflow.missionState(task.id)" in source
    assert "window.DevPilotGameWorkflow.watch(task.id" in source
    assert "window.state" not in source
    assert "localStorage.setItem" not in source
    assert "game_state === 'MISSION_COMPLETE'" in source
    assert "game_state === 'SHIELD_BLOCKED'" in source


def test_workflow_bridge_is_game_only_not_global_boot():
    loader = LOADER.read_text(encoding="utf-8")
    prefix = loader.split("game: [", 1)[0]

    assert "game-workflow-adapter.js" not in prefix
    assert "game-workflow-ui.js" not in prefix
    assert "devpilot:authenticated-ui-ready" not in ADAPTER.read_text(encoding="utf-8")
    assert "devpilot:authenticated-ui-ready" not in BRIDGE.read_text(encoding="utf-8")
