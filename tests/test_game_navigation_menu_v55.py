from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/game-shell.css").read_text(encoding="utf-8")
APP = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

DASHBOARD_VIEWS = (
    "overview",
    "organizations",
    "projects",
    "tasks",
    "providers",
    "reports",
    "audit",
)


def test_standalone_game_exposes_complete_core_navigation():
    assert 'id="game-menu-toggle"' in INDEX
    assert 'id="game-menu"' in INDEX
    assert 'aria-controls="game-menu"' in INDEX
    for view in DASHBOARD_VIEWS:
        assert f'data-game-dashboard-view="{view}"' in INDEX
    assert 'aria-current="page">Modo Jogo' in INDEX


def test_menu_navigation_is_explicit_and_restored_after_dashboard_auth():
    assert "sessionStorage.setItem('devpilot-dashboard-view', target)" in BOOT
    assert "sessionStorage.getItem('devpilot-dashboard-view')" in APP
    assert "sessionStorage.removeItem('devpilot-dashboard-view')" in APP
    assert "document.getElementById(`${requestedView}-view`)" in APP


def test_menu_is_keyboard_accessible_without_observers():
    assert "event.key === 'Escape'" in BOOT
    assert "aria-expanded" in INDEX
    assert ".devpilot-game-menu[hidden]" in CSS
    navigation_setup = BOOT[:BOOT.index("function showBooting")]
    assert "MutationObserver" not in navigation_setup
