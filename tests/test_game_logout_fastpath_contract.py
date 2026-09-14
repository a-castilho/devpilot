from pathlib import Path


BOOT = Path("app/static/game/game-bootstrap.js")


def test_game_logout_uses_capture_fast_path_without_reload_loop():
    source = BOOT.read_text(encoding="utf-8")
    assert "#logout" in source
    assert "stopImmediatePropagation" in source
    assert "localStorage.removeItem('devpilot-token')" in source
    assert "sessionStorage.clear()" in source
    assert "window.location.replace('/')" in source
    assert "location.reload()" not in source


def test_game_logout_is_idempotent_and_gives_immediate_feedback():
    source = BOOT.read_text(encoding="utf-8")
    assert "logoutInProgress" in source
    assert "button.disabled=true" in source
    assert "button.textContent='Saindo…'" in source
    assert "devpilot:logout" in source
