from pathlib import Path


VIEWPORT = Path("app/static/viewport-adaptive-v15.js")
LEGACY = Path("app/static/executions-submit-v29.js")
CANONICAL = Path("app/static/task-modal.js")


def test_viewport_no_longer_loads_v29_submit():
    source = VIEWPORT.read_text(encoding="utf-8")
    assert "loadExecutionsSubmitV29" not in source
    assert "executions-submit-v29.js" not in source


def test_v29_is_inert_stub_only():
    source = LEGACY.read_text(encoding="utf-8")
    assert "__devpilotExecutionsSubmitV29Retired" in source
    assert "addEventListener('submit'" not in source
    assert 'addEventListener("submit"' not in source
    assert "apiJson('/tasks'" not in source
    assert 'apiJson("/tasks"' not in source
    assert "fetch(`/api${path}`" not in source


def test_task_modal_remains_canonical_and_normalizes_source():
    source = CANONICAL.read_text(encoding="utf-8")
    assert "__devpilotCanonicalExecutionSubmitV30" in source
    assert "function canonicalSource(value)" in source
    assert "source: canonicalSource(" in source
    assert "form.addEventListener('submit', saveExecution, true)" in source
