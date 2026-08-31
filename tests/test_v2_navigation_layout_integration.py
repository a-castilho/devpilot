from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_v2_pipeline_and_latest_navigation_coexist():
    game = (STATIC / "build-game.js").read_text(encoding="utf-8")
    observability = (STATIC / "task-workflow-observability.js").read_text(encoding="utf-8")
    index = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "[DEVPILOT_BUILD_GAME_PIPELINE_V2]" in game
    assert "Entrega e revisão" in game
    assert "projectById(selectedProjectId)?.description" not in game
    assert "missionTasks.length ? historicalGoal : storedGoal" in game

    assert "Worker de tarefas ativo" in observability
    assert "GitHub Actions Runner" in observability

    assert 'class="mobile-nav"' in index
    assert "page-navigation-v26.css" in index
    assert "simplified-nav.css" in index
    assert "mobile-accordion-menu.css" in index


def test_latest_responsive_navigation_assets_are_present():
    required = [
        "simplified-nav.js",
        "mobile-accordion-menu.js",
        "page-navigation-v26.js",
        "sidebar-responsive-v16.css",
        "sidebar-state-v24.css",
        "layout-authority-v37.css",
        "layout-scale-v36.css",
    ]
    missing = [name for name in required if not (STATIC / name).is_file()]
    assert missing == []
