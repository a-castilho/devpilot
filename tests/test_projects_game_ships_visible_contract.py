from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DELETE = (ROOT / "app/static/project-delete-ui.js").read_text(encoding="utf-8")
FEATURE_LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
MOBILE_MENU = (ROOT / "app/static/mobile-accordion-menu.js").read_text(encoding="utf-8")
GAME_INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_light_projects_runtime_restores_ship_after_base_cards_render():
    assert "project-lite-ship-hangar" in PROJECT_DELETE
    assert "function ensureShipAndGame" in PROJECT_DELETE
    assert "MutationObserver(() => decorateProjects())" in PROJECT_DELETE
    assert "wrapRenderer('renderProjects', decorateProjects)" in PROJECT_DELETE
    assert "document.addEventListener('devpilot:view-changed'" in PROJECT_DELETE


def test_each_project_gets_direct_game_button_and_project_context():
    assert "data.projectGame" not in PROJECT_DELETE
    assert "button.dataset.projectGame = project.id" in PROJECT_DELETE
    assert "devpilot-build-game-project" in PROJECT_DELETE
    assert "devpilot-build-game-mission" in PROJECT_DELETE
    assert "window.location.assign(GAME_URL)" in PROJECT_DELETE


def test_mobile_projects_runtime_has_permanent_game_navigation_recovery():
    assert "data-simple-game" in PROJECT_DELETE
    assert "Modo Jogo" in PROJECT_DELETE
    assert "devpilot-game-nav-five" in PROJECT_DELETE
    assert "repeat(5,minmax(0,1fr))" in PROJECT_DELETE


def test_light_bundle_always_loads_the_repair_module():
    assert "PROJECTS_LIGHT_FILES" in FEATURE_LOADER
    assert "'project-delete-ui.js'" in FEATURE_LOADER
    assert "mobileShell: ['mobile-accordion-menu.js']" in FEATURE_LOADER


def test_standalone_game_document_is_still_available():
    assert "/assets/build-game.js" in GAME_INDEX
    assert "/assets/game/game-bootstrap.js" in GAME_INDEX
