from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/static/mobile-project-card-compact.js").read_text(encoding="utf-8")


def test_low_power_projects_keep_ship_visuals_without_loading_heavy_runtime():
    assert "project-lite-ship-hangar" in SOURCE
    assert "project-lite-ship-svg" in SOURCE
    assert "shipLiteEnhanced" in SOURCE
    assert "card.dataset.shipEnhanced = '1'" not in SOURCE
    assert "const batchSize = () => lowPower() ? 6 : 15;" in SOURCE
    assert "content-visibility:auto" in SOURCE


def test_every_project_card_gets_game_entry():
    assert "data-project-game" in SOURCE
    assert "button.textContent = 'Jogar'" in SOURCE
    assert "const GAME_PROJECT_KEY = 'devpilot-build-game-project';" in SOURCE
    assert "const GAME_URL = '/game/index.html';" in SOURCE
    assert "window.location.assign(GAME_URL)" in SOURCE


def test_switching_project_does_not_reuse_another_projects_mission():
    assert "const GAME_MISSION_KEY = 'devpilot-build-game-mission';" in SOURCE
    assert "previous && previous !== id" in SOURCE
    assert "localStorage.removeItem(GAME_MISSION_KEY)" in SOURCE
    assert "localStorage.setItem(GAME_PROJECT_KEY, id)" in SOURCE


def test_mobile_project_loader_keeps_previous_stall_protections():
    assert "const controller = new AbortController();" in SOURCE
    assert "controller.abort()" in SOURCE
    assert "12000" in SOURCE
    assert "data-projects-retry" in SOURCE
    assert "data-projects-load-more" in SOURCE
