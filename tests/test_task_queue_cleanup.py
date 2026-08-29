from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_queued_cleanup_is_super_admin_only_and_preserves_started_tasks():
    routes = read("app/task_run_routes.py")

    assert '@router.delete("/tasks/queued")' in routes
    assert "Depends(require_roles(Role.SUPER_ADMIN))" in routes
    assert "Task.status == TaskStatus.queued" in routes
    assert "~Task.runs.any()" in routes
    assert 'action="task.queued_deleted"' in routes
    assert "db.delete(task)" in routes


def test_task_cleanup_ui_is_loaded_only_with_tasks_feature():
    loader = read("app/static/feature-loader.js")
    cleanup = read("app/static/task-queue-cleanup.js")

    tasks_bundle = loader.split("tasks: [", 1)[1].split("],", 1)[0]
    assert "task-queue-cleanup.js" in tasks_bundle
    assert "api('/tasks/queued', {method: 'DELETE'})" in cleanup
    assert "SUPER_ADMIN" in cleanup
    assert "loadAllTasks(true)" in cleanup
    assert "loadDashboard()" in cleanup
