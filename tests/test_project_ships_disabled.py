from pathlib import Path


PROJECT_SHIPS = Path("app/static/project-ships.js")


def test_project_ship_effects_are_disabled_without_click_handlers_or_observers():
    source = PROJECT_SHIPS.read_text(encoding="utf-8")

    assert "window.__devpilotProjectShipsDisabled = true" in source
    assert "new MutationObserver" not in source
    assert "requestAnimationFrame" not in source
    assert "setInterval" not in source
    assert "addEventListener('click'" not in source


def test_project_ship_cleanup_preserves_functional_project_cards():
    source = PROJECT_SHIPS.read_text(encoding="utf-8")

    assert "project-ship-hangar" in source
    assert "project-visual-overview" in source
    assert "project-ship-card" in source
    assert ".remove()" in source
    assert "card.remove()" not in source
