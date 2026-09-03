from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWPORT = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_new_project_no_longer_has_window_capture_owner():
    assert "[data-project-builder-open]" not in VIEWPORT
    assert "openProjectBuilderSafe" not in VIEWPORT
    assert "__devpilotPrimaryActionSafeOpenV29" not in VIEWPORT


def test_new_project_uses_canonical_nonblocking_loader():
    assert "async function openProjectBuilderDirect" in LOADER
    assert "showProjectBuilderImmediately();" in LOADER
    assert "await loadFeature('projectBuilder')" in LOADER


def test_new_project_has_local_view_fallback_in_feature_loader():
    block = LOADER.split("function showProjectBuilderImmediately()", 1)[1].split("async function openProjectBuilderDirect", 1)[0]
    assert "showView('new-project')" in block
    assert "view.id === 'new-project-view'" in block
