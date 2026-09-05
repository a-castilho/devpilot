from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENU = (ROOT / "app/static/mobile-accordion-menu.js").read_text(encoding="utf-8")
RUNTIME = (ROOT / "app/static/mobile-game-ships-stable.js").read_text(encoding="utf-8")


def test_mobile_bottom_navigation_has_direct_game_entry():
    assert "data-simple-game" in MENU
    assert "<small>Jogo</small>" in MENU
    assert "grid-template-columns:repeat(5" in MENU
    assert "window.location.assign('/game/index.html')" in MENU


def test_mobile_shell_does_not_hidden_load_game_ships_runtime():
    assert "mobile-game-ships-stable.js" not in MENU
    assert "ensureGameShipsRuntime" not in MENU
    assert "document.createElement('script')" not in MENU


def test_project_cards_runtime_uses_scoped_projects_observer():
    assert "project-game-ship-stable" in RUNTIME
    assert "projectsObserver = new MutationObserver" in RUNTIME
    assert "projectsObserver.observe(host" in RUNTIME
    assert "document.documentElement" not in RUNTIME
    assert "decorateCards()" in RUNTIME
    assert "[data-project-task]" in RUNTIME


def test_project_cards_runtime_keeps_direct_game_button_contract():
    assert "button.dataset.projectGameStable = id" in RUNTIME
    assert "[data-project-game-stable]" in RUNTIME
    assert "🎮 Jogar" in RUNTIME
    assert "devpilot-build-game-project" in RUNTIME
    assert "window.location.assign(GAME_URL)" in RUNTIME
