from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_JS = (ROOT / "app/static/task-completion-documentation.js").read_text(encoding="utf-8")
TASK_CSS = (ROOT / "app/static/task-development-v2.css").read_text(encoding="utf-8")
BUILD_GAME_JS = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")


def test_v2_pipeline_remains_authoritative():
    assert "[DEVPILOT_BUILD_GAME_PIPELINE_V2]" in BUILD_GAME_JS
    assert "Entrega e revisão" in BUILD_GAME_JS


def test_legacy_game_tasks_are_separated_when_v2_exists():
    assert "isLegacyGameTask" in TASK_JS
    assert "isV2GameTask" in TASK_JS
    assert "shouldHideLegacyGameTask" in TASK_JS
    assert "data-task-legacy-game" not in TASK_JS.lower()  # dataset API is used instead of raw markup
    assert "taskLegacyGame" in TASK_JS


def test_mobile_task_actions_have_single_grid_authority():
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in TASK_CSS
    assert "grid-template-columns:minmax(0,1fr)!important" in TASK_CSS
    assert "position:static!important" in TASK_CSS
    assert "white-space:normal!important" in TASK_CSS
    assert "#tasks-view .task-action-auto" in TASK_CSS
