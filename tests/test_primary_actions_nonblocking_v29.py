from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORT = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")


def test_primary_actions_are_intercepted_at_window_capture():
    assert "window.addEventListener('click'" in VIEWPORT
    assert "[data-project-builder-open]" in VIEWPORT
    assert "[data-open=\"task-modal\"]" in VIEWPORT
    assert "event.stopImmediatePropagation()" in VIEWPORT


def test_new_project_opens_before_lazy_loading():
    block = VIEWPORT.split("function openProjectBuilderSafe()", 1)[1]
    assert "devpilotNavigate('new-project'" in block
    assert "__devpilotLoadFeature('projectBuilder')" in block
    assert block.index("devpilotNavigate('new-project'") < block.index("__devpilotLoadFeature('projectBuilder')")


def test_new_execution_opens_modal_without_waiting_for_bundle():
    block = VIEWPORT.split("function openTaskModalSafe", 1)[1]
    assert "modal.showModal" in block
    assert "__devpilotLoadFeature('taskModal')" in block
    assert block.index("modal.showModal") < block.index("__devpilotLoadFeature('taskModal')")
