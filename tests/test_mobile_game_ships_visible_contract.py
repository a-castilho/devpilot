from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENU = (ROOT / "app/static/mobile-accordion-menu.js").read_text(encoding="utf-8")
RUNTIME = (ROOT / "app/static/mobile-game-ships-stable.js").read_text(encoding="utf-8")


def test_mobile_bottom_navigation_has_direct_game_entry():
    assert "data-simple-game" in MENU
    assert "<small>Jogo</small>" in MENU
    assert "grid-template-columns:repeat(5" in MENU
    assert "window.location.assign('/game/index.html')" in MENU


def test_mobile_shell_loads_game_ships_runtime_directly():
    assert "mobile-game-ships-stable.js" in MENU
    assert "ensureGameShipsRuntime()" in MENU


def test_project_cards_get_visible_spaceships_even_after_initial_render():
    assert "project-game-ship-stable" in RUNTIME
    assert "MutationObserver(scheduleSync)" in RUNTIME
    assert "decorateCards()" in RUNTIME
    assert "[data-project-task]" in RUNTIME


def test_project_cards_get_direct_game_button():
    assert "dataProjectGameStable" in RUNTIME
    assert "🎮 Jogar" in RUNTIME
    assert "devpilot-build-game-project" in RUNTIME
    assert "window.location.assign(GAME_URL)" in RUNTIME
