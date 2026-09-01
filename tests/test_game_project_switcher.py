from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(path: str) -> str:
    return (STATIC / path).read_text(encoding="utf-8")


def test_game_neon_exposes_existing_project_select_inside_mission_card():
    source = read("game/project-switcher.js")
    assert "#build-game-project" in source
    assert "game-neon-mission" in source
    assert "replaceChildren(select)" in source
    assert "dispatchEvent(new Event('change'" in source
    assert "data-game-project-prev" in source
    assert "data-game-project-next" in source


def test_projects_bottom_nav_stays_inside_game_and_focuses_switcher():
    source = read("game/project-switcher.js")
    assert '[data-game-nav="projects"]' in source
    assert "event.stopImmediatePropagation()" in source
    assert "focusSwitcher()" in source


def test_game_v50_loads_project_switcher_before_bootstrap():
    html = read("game/index.html")
    assert "game-v50-20260901" in html
    switcher = html.index("/assets/game/project-switcher.js")
    bootstrap = html.index("/assets/game/game-bootstrap.js")
    assert switcher < bootstrap
