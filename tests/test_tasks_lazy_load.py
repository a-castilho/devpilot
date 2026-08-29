from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_dashboard_starts_with_twenty_task_summaries():
    app = read("app/static/app.js")
    dashboard = app.split("async function loadDashboard()", 1)[1].split("async function loadProjects()", 1)[0]
    assert "api('/ui/tasks?limit=20')" in dashboard
    assert "api('/tasks?limit=20')" not in dashboard


def test_task_history_is_owned_by_core_app_and_uses_lightweight_summary_endpoint():
    app = read("app/static/app.js")
    main = read("app/main.py")

    assert "api('/ui/tasks?limit=20')" in app
    assert "async function loadAllTasks" in app
    assert '"tasks-lazy-load.js"' not in main


def test_large_prompt_is_loaded_only_for_one_explicit_task():
    app = read("app/static/app.js")
    routes = read("app/frontend_ui_routes.py")

    assert "loadTaskInstructions" in app
    assert "api(`/ui/tasks/${encodeURIComponent(taskId)}`)" in app
    assert '@router.get("/tasks/{task_id}")' in routes
    assert '"prompt": item.prompt' in routes


def test_task_pagination_does_not_reintroduce_legacy_bulk_endpoint():
    app = read("app/static/app.js")

    assert "api('/tasks?limit=500')" not in app
    assert "api('/tasks?limit=20')" not in app
    assert "api('/ui/tasks?limit=20')" in app
