from pathlib import Path


TASK_MODAL = Path("app/static/task-modal.js")
APP = Path("app/static/app.js")
SCHEMAS = Path("app/schemas.py")


def test_execution_modal_takes_single_submit_ownership_without_blocking_event_chain():
    modal = TASK_MODAL.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")

    # app.js ainda contém o handler histórico porque também concentra o shell.
    # O módulo canônico de execução o desliga explicitamente ao carregar.
    assert "if (taskForm) taskForm.onsubmit = async event =>" in app
    assert "form.onsubmit = null;" in modal
    assert "window.__devpilotCanonicalExecutionSubmitV34" in modal
    assert "form.addEventListener('submit', saveExecution);" in modal
    assert "event.stopImmediatePropagation()" not in modal


def test_development_mode_reuses_existing_task_pipeline():
    modal = TASK_MODAL.read_text(encoding="utf-8")
    schemas = SCHEMAS.read_text(encoding="utf-8")

    assert "develop: {" in modal
    assert "[DEVPILOT_MODE=${selectedMode}]" in modal
    assert "const created = await apiJson('/tasks'" in modal
    assert "source: canonicalSource(form.closest('dialog')?.dataset.taskSource)" in modal
    assert 'class TaskCreate(BaseModel):' in schemas
    assert 'pattern=r"^(dashboard|voice|api)$"' in schemas


def test_execution_submit_keeps_persistence_confirmation_and_refresh():
    modal = TASK_MODAL.read_text(encoding="utf-8")

    assert "const persisted = await verifyCreated(id);" in modal
    assert "devpilot:execution-created" in modal
    assert "await refreshExecutions();" in modal
