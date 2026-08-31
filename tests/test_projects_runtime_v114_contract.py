from pathlib import Path


def test_projects_runtime_loads_ship_and_mobile_compact_layers():
    loader = Path("app/static/acs-loader.js").read_text(encoding="utf-8")
    assert "ensureProjectsRuntime" in loader
    assert "project-ships.js" in loader
    assert "mobile-project-card-compact.js" in loader
    assert 'data-view="projects"' in loader
    assert "devpilot:projects-runtime-ready" in loader


def test_projects_ship_layer_still_enhances_original_cards():
    ships = Path("app/static/project-ships.js").read_text(encoding="utf-8")
    assert "project-ship-card" in ships
    assert "MutationObserver" in ships


def test_pipeline_v2_remains_present_in_same_release():
    game = Path("app/static/build-game.js").read_text(encoding="utf-8")
    assert "DEVPILOT_BUILD_GAME_PIPELINE_V2" in game
    assert "Planejamento" in game
    assert "Entrega e revisão" in game
