from pathlib import Path


BOOT = Path("app/static/game/game-bootstrap.js")


def test_game_exit_stops_active_runtime_before_navigation():
    source = BOOT.read_text(encoding="utf-8")
    assert "leavingGame" in source
    assert "devpilot:game:leaving" in source
    assert "window.stop()" in source
    assert "button.disabled=true" in source
    assert "button.setAttribute('aria-busy','true')" in source
    assert "window.location.replace('/')" in source


def test_game_exit_has_its_own_fast_path_instead_of_raw_replace_handler():
    source = BOOT.read_text(encoding="utf-8")
    assert "leaveStandaloneGame" in source
    assert "addEventListener('click',()=>leaveStandaloneGame" in source
