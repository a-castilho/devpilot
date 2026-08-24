from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_task_analytics_fallback_matches_active_task_renderer_rows():
    analytics = read("app/static/task-analytics.js")
    renderer = read("app/static/task-failures.js")

    assert "#tasks-table tr[data-task-id]" in analytics
    assert "#tasks-table tr.task-main-row[data-task-id]" in analytics
    assert 'return `<tr data-task-id="${esc(task.id)}">' in renderer


def test_task_analytics_uses_rendered_rows_when_state_is_empty_or_divergent():
    script = read("app/static/task-analytics.js")

    assert "const tasksFromTable = () =>" in script
    assert "if (!stateTasks.length && tableTasks.length) return tableTasks" in script
    assert "if (tableTasks.length && tableTasks.length !== stateTasks.length) return tableTasks" in script
    assert "return stateTasks.length ? stateTasks : tableTasks" in script


def test_task_analytics_refreshes_when_rendered_table_changes():
    script = read("app/static/task-analytics.js")

    assert "new MutationObserver" in script
    assert "window.renderTaskAnalytics()" in script
    assert "analyticsObserved" in script
