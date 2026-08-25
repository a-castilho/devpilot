from pathlib import Path

from app.main import _FEATURE_AUTHENTICATED_SCRIPTS

SOURCE = Path(__file__).resolve().parents[1] / "app" / "static" / "task-analytics.js"


def test_task_analytics_does_not_start_build_game_duplicate():
    text = SOURCE.read_text(encoding="utf-8")
    assert "script.src = '/assets/build-game.js" not in text
    assert "data-build-game-loader" not in text


def test_task_analytics_never_auto_loads_game_assets():
    text = SOURCE.read_text(encoding="utf-8")
    assert "LEGACY_GAME_EXTRAS" not in text
    assert "loadLegacyExtras" not in text
    assert "devpilot:authenticated-ui-ready" not in text
    assert "system-tests.js" not in text
    assert "build-game-subphases.js" not in text
    assert "build-game-new-session.js" not in text
    assert "build-game-url-bonus.js" not in text
    assert "build-game-weapons.js" not in text


def test_game_extras_belong_to_explicit_game_feature_group():
    game = _FEATURE_AUTHENTICATED_SCRIPTS["game"]
    assert "system-tests.js" in game
    assert "build-game-subphases.js" in game
    assert "build-game-new-session.js" in game
    assert "build-game-url-bonus.js" in game
    assert "build-game-weapons.js" in game
