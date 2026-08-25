from pathlib import Path


TASK_ANALYTICS = Path("app/static/task-analytics.js")


def test_game_extras_do_not_start_on_authenticated_ui_ready():
    source = TASK_ANALYTICS.read_text(encoding="utf-8")
    assert "__devpilotLoadGameExtras" in source
    assert "devpilot:game-open" in source
    assert "isGameIntent" in source
    assert "document.addEventListener('click'" in source
    assert "document.addEventListener('devpilot:authenticated-ui-ready', start" not in source


def test_task_analytics_does_not_repaint_hidden_view_on_every_mutation():
    source = TASK_ANALYTICS.read_text(encoding="utf-8")
    assert "document.querySelector('#tasks-view.active')" in source
    assert "if (document.querySelector('#tasks-view.active')) window.renderTaskAnalytics();" in source
