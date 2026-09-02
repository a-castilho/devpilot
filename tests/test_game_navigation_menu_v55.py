from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/game-shell.css").read_text(encoding="utf-8")


def test_standalone_game_keeps_navigation_minimal():
    assert 'id="game-exit"' in INDEX
    assert 'aria-label="Sair do modo jogo"' in INDEX
    assert 'id="game-menu-toggle"' not in INDEX
    assert 'id="game-menu"' not in INDEX
    assert 'data-game-dashboard-view=' not in INDEX


def test_exit_navigation_is_explicit_and_does_not_depend_on_dashboard_state():
    assert "const backToDashboard = () => window.location.assign('/')" in BOOT
    assert "document.getElementById('game-exit')?.addEventListener('click', backToDashboard)" in BOOT
    assert "sessionStorage.setItem('devpilot-dashboard-view'" not in BOOT


def test_minimal_navigation_has_no_observer_or_hidden_menu_keyboard_state():
    assert "MutationObserver" not in BOOT
    assert "game-menu" not in BOOT
    assert ".devpilot-game-hud" in CSS
    assert ".devpilot-game-exit" in CSS
