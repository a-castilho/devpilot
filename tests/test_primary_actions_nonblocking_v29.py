from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORT = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_window_capture_is_reserved_for_new_execution_only():
    assert "window.addEventListener('click'" in VIEWPORT
    assert "[data-open=\"task-modal\"]" in VIEWPORT
    assert "[data-project-builder-open]" not in VIEWPORT
    assert "__devpilotTaskActionSafeOpenV41" in VIEWPORT


def test_new_project_is_owned_by_feature_loader_single_path():
    assert "const projectBuilderTrigger = target.closest('[data-project-builder-open]');" in LOADER
    assert "void openProjectBuilderDirect(projectBuilderTrigger);" in LOADER
    assert "[data-project-builder-open]" not in VIEWPORT


def test_new_project_opens_before_lazy_loading():
    block = LOADER.split("async function openProjectBuilderDirect", 1)[1].split("async function analyzeProjectDirect", 1)[0]
    assert block.index("showProjectBuilderImmediately();") < block.index("await loadFeature('projectBuilder')")


def test_new_execution_opens_modal_without_waiting_for_bundle():
    block = VIEWPORT.split("function openTaskModalSafe", 1)[1]
    assert "modal.showModal" in block
    assert "__devpilotLoadFeature('taskModal')" in block
    assert block.index("modal.showModal") < block.index("__devpilotLoadFeature('taskModal')")
