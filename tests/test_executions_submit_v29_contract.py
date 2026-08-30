from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "app" / "static" / "executions-submit-v29.js"
VIEWPORT = ROOT / "app" / "static" / "viewport-adaptive-v15.js"
API = ROOT / "app" / "api.py"


def test_v29_uses_capture_submit_and_posts_once():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "__devpilotExecutionsSubmitV29" in text
    assert "document.addEventListener('submit', intercept, true)" in text
    assert "apiJson('/tasks'" in text
    assert "method: 'POST'" in text
    assert "stopImmediatePropagation" in text


def test_v29_verifies_persistence_after_create():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "verifyCreated" in text
    assert "/ui/tasks/${encodeURIComponent(id)}" in text
    assert "Execução salva com sucesso." in text
    assert "não pôde ser confirmada após a gravação" in text


def test_backend_create_task_commits():
    text = API.read_text(encoding="utf-8")
    assert '@router.post("/tasks", status_code=201)' in text
    assert "def create_task(" in text
    assert "db.add(item)" in text
    assert "db.commit()" in text


def test_v29_is_loaded_after_previous_execution_layers():
    text = VIEWPORT.read_text(encoding="utf-8")
    assert "loadExecutionsSubmitV29" in text
    assert "executions-submit-v29.js" in text
    assert text.index("loadExecutionResultsV28();") < text.index("loadExecutionsSubmitV29();")


if __name__ == "__main__":
    test_v29_uses_capture_submit_and_posts_once()
    test_v29_verifies_persistence_after_create()
    test_backend_create_task_commits()
    test_v29_is_loaded_after_previous_execution_layers()
    print("OK: executions submit V29 contract")
