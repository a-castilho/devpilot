from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_task_analytics_can_recover_from_rendered_task_table():
    script = read("app/static/task-analytics.js")
    assert "const tasksFromTable = () =>" in script
    assert "#tasks-table tr.task-main-row" in script
    assert "const analyticsTasks = () =>" in script
    assert "return stateTasks.length ? stateTasks : tableTasks" in script


def test_task_analytics_refreshes_when_task_table_changes():
    script = read("app/static/task-analytics.js")
    assert "new MutationObserver" in script
    assert "window.renderTaskAnalytics()" in script
    assert "analyticsObserved" in script


def test_task_analytics_normalizes_status_before_counting_active_tasks():
    script = read("app/static/task-analytics.js")
    assert "normalizeStatus(task.status) === 'completed'" in script
    assert "['queued','running','review'].includes(normalizeStatus(task.status))" in script
