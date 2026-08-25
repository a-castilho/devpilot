from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "app" / "static" / "task-analytics.js"


def test_task_analytics_does_not_start_build_game_duplicate():
    text = SOURCE.read_text(encoding="utf-8")
    assert "script.src = '/assets/build-game.js" not in text
    assert "data-build-game-loader" not in text


def test_legacy_game_extras_wait_for_authenticated_ui_ready():
    text = SOURCE.read_text(encoding="utf-8")
    assert "devpilot:authenticated-ui-ready" in text
    assert "requestIdleCallback" in text
    assert "await sleep(450)" in text
    assert "system-tests.js" in text
    assert "build-game-subphases.js" in text
    assert "build-game-new-session.js" in text
    assert "build-game-url-bonus.js" in text
    assert "build-game-weapons.js" in text


def test_legacy_game_extras_are_loaded_serially():
    text = SOURCE.read_text(encoding="utf-8")
    assert "for (const asset of LEGACY_GAME_EXTRAS)" in text
    assert "await loadAsset(asset);" in text
    assert "await sleep(450);" in text
