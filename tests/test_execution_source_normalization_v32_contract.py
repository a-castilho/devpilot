from pathlib import Path


TASK_MODAL = Path("app/static/task-modal.js")
SCHEMAS = Path("app/schemas.py")


def test_execution_submit_normalizes_ui_source_to_backend_contract():
    modal = TASK_MODAL.read_text(encoding="utf-8")
    schemas = SCHEMAS.read_text(encoding="utf-8")

    assert "function canonicalSource(value)" in modal
    assert "source === 'voice' || source === 'api' ? source : 'dashboard'" in modal
    assert "source: canonicalSource(form.closest('dialog')?.dataset.taskSource)" in modal
    assert 'pattern=r"^(dashboard|voice|api)$"' in schemas


def test_visual_navigation_sources_are_not_sent_raw_to_task_create():
    modal = TASK_MODAL.read_text(encoding="utf-8")

    assert "source: form.closest('dialog')?.dataset.taskSource || 'dashboard'" not in modal
