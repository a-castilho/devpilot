from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_dashboard_starts_with_only_five_task_summaries():
    app = read("app/static/app.js")
    dashboard = app.split("async function loadDashboard()", 1)[1].split("async function loadProjects()", 1)[0]
    assert "api('/ui/tasks?limit=5')" in dashboard
    assert "api('/tasks?limit=5')" not in dashboard


def test_task_history_uses_lightweight_summary_endpoint():
    app = read("app/static/app.js")
    script = read("app/static/tasks-lazy-load.js")

    assert "api('/ui/tasks?limit=20')" in app
    assert "api(`/ui/tasks?limit=${nextLimit}`)" in script
    assert "api(`/tasks?limit=${nextLimit}`)" not in script
    assert "Carregar mais ${PAGE_SIZE} tarefas" in script


def test_large_prompt_is_loaded_only_for_one_explicit_task():
    app = read("app/static/app.js")
    routes = read("app/frontend_ui_routes.py")

    assert "loadTaskInstructions" in app
    assert "api(`/ui/tasks/${encodeURIComponent(taskId)}`)" in app
    assert '@router.get("/tasks/{task_id}")' in routes
    assert '"prompt": item.prompt' in routes


def test_lazy_loader_is_loaded_by_spa_runtime():
    main = read("app/main.py")
    assert '"tasks-lazy-load.js"' in main
