from pathlib import Path

SHELL = Path("app/static/game-shell.js")
CSS = Path("app/static/game-shell.css")


def test_mobile_game_exit_has_touch_first_handler_and_click_fallback():
    source = SHELL.read_text(encoding="utf-8")
    assert ".devpilot-game-exit" in source
    assert "touchstart" in source
    assert "passive: false" in source
    assert "preventDefault()" in source
    assert "leaveGameToOverview" in source
    assert "exitInProgress" in source


def test_mobile_game_exit_remains_interactive_above_game_stage():
    source = CSS.read_text(encoding="utf-8")
    assert ".devpilot-game-exit" in source
    assert "pointer-events:auto" in source
    assert "z-index:1000" in source
