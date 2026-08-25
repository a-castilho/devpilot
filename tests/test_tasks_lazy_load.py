from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_dashboard_starts_with_only_five_tasks():
    app = read("app/static/app.js")
    assert "api('/tasks?limit=5')" in app


def test_automatic_full_history_load_is_blocked():
    script = read("app/static/tasks-lazy-load.js")
    assert "if(!explicitLoading)return" in script
    assert "PAGE_SIZE=20" in script
    assert "MAX_LIMIT=500" in script
    assert "api(`/tasks?limit=${nextLimit}`)" in script
    assert "'/tasks?limit=500'" not in script


def test_task_history_requires_explicit_progressive_click():
    script = read("app/static/tasks-lazy-load.js")
    assert "Carregar mais ${PAGE_SIZE} tarefas" in script
    assert "button.addEventListener('click'" in script
    assert "explicitLoading=true" in script


def test_long_task_prompts_are_hydrated_only_when_opened():
    script = read("app/static/tasks-lazy-load.js")
    assert "Abra para carregar as instruções." in script
    assert "data-task-instructions" in script
    assert "hydrateInstruction" in script
    assert "table.addEventListener('toggle'" in script


def test_lazy_loader_is_loaded_by_spa_runtime():
    main = read("app/main.py")
    assert "tasks-lazy-load.js" in main
