from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_dashboard_starts_with_only_five_tasks():
    app = read("app/static/app.js")
    assert "api('/tasks?limit=5')" in app


def test_full_task_history_requires_explicit_button_click():
    script = read("app/static/tasks-lazy-load.js")
    assert "const originalLoadAllTasks=loadAllTasks" in script
    assert "if(!allowAll)return" in script
    assert "Ver todas as tarefas" in script
    assert "button.addEventListener('click'" in script
    assert "allowAll=true" in script


def test_lazy_loader_is_loaded_by_spa_runtime():
    main = read("app/main.py")
    assert '/assets/tasks-lazy-load.js' in main
