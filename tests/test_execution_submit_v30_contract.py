from pathlib import Path


TASK_MODAL = Path("app/static/task-modal.js")
LEGACY_SUBMIT = Path("app/static/executions-submit-v29.js")
API = Path("app/api.py")


def test_task_modal_owns_canonical_execution_submit():
    source = TASK_MODAL.read_text(encoding="utf-8")
    assert "__devpilotCanonicalExecutionSubmitV30" in source
    assert "form.addEventListener('submit', saveExecution, true)" in source
    assert "apiJson('/tasks'" in source
    assert "method: 'POST'" in source
    assert "verifyCreated(id)" in source
    assert "Execução salva com sucesso." in source
    assert "NOVA EXECUÇÃO" in source


def test_legacy_v29_yields_to_canonical_v30():
    source = LEGACY_SUBMIT.read_text(encoding="utf-8")
    assert "if (window.__devpilotCanonicalExecutionSubmitV30) return;" in source


def test_backend_still_commits_task_creation():
    source = API.read_text(encoding="utf-8")
    assert '@router.post("/tasks", status_code=201)' in source
    assert "db.add(item)" in source
    assert "db.commit()" in source
