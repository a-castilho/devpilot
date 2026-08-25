from pathlib import Path

from app.main import spa


ROOT = Path(__file__).resolve().parents[1]
FEATURE_LOADER = ROOT / "app" / "static" / "feature-loader.js"
ADAPTER = ROOT / "app" / "static" / "game-workflow-adapter.js"
BRIDGE = ROOT / "app" / "static" / "game-workflow-ui.js"
GAME = ROOT / "app" / "static" / "build-game.js"


def test_mobile_shell_keeps_game_out_of_initial_boot():
    rendered = spa("mobile").body.decode("utf-8")

    assert '<body class="mobile-route">' in rendered
    assert "/assets/feature-loader.js?v=" in rendered
    assert "/assets/game-workflow-adapter.js?v=" not in rendered
    assert "/assets/game-workflow-ui.js?v=" not in rendered
    assert "/assets/build-game.js?v=" not in rendered


def test_mobile_game_bundle_loads_real_workflow_in_safe_order():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")
    game_bundle = loader.split("game: [", 1)[1].split("],", 1)[0]

    adapter = game_bundle.index("'game-workflow-adapter.js'")
    game = game_bundle.index("'build-game.js'")
    bridge = game_bundle.index("'game-workflow-ui.js'")
    assert adapter < game < bridge


def test_mobile_game_uses_real_task_run_state_and_authorization_shield():
    adapter = ADAPTER.read_text(encoding="utf-8")
    bridge = BRIDGE.read_text(encoding="utf-8")

    assert "/api/task-runs/latest?limit=500" in adapter
    assert "/api/task-runs/${encodeURIComponent(summary.run_id)}" in adapter
    assert "/api/tasks/${encodeURIComponent(taskId)}/retry" in adapter
    assert "awaiting_approval" in adapter
    assert "SHIELD_BLOCKED" in adapter
    assert "requires_authorization" in adapter
    assert "/api/game/" not in adapter
    assert "window.state" not in bridge
    assert "localStorage.setItem" not in bridge


def test_game_remains_touch_friendly_on_small_screens():
    source = GAME.read_text(encoding="utf-8")

    assert "@media(max-width:800px)" in source
    assert ".build-game-config{grid-template-columns:1fr}" in source
    assert ".build-game-phase-actions button{width:100%}" in source
    assert "min-height:44px" in source
