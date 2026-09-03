from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")


def test_new_project_safe_open_runs_in_capture_phase():
    assert "__devpilotNewProjectSafeOpenV28" in SOURCE
    assert "closest('[data-project-builder-open]')" in SOURCE
    assert "event.stopImmediatePropagation()" in SOURCE
    assert "}, true);" in SOURCE


def test_new_project_safe_open_uses_central_nonblocking_navigation():
    assert "window.devpilotNavigate('new-project'" in SOURCE
    assert "new-project-safe-open" in SOURCE


def test_new_project_safe_open_has_local_fallback():
    assert "window.showView('new-project')" in SOURCE
    assert "view.id === 'new-project-view'" in SOURCE
