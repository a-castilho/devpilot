from pathlib import Path


SOURCE = Path("app/static/acs-loader.js").read_text(encoding="utf-8")


def test_mobile_projects_bypass_heavy_feature_bundle():
    assert "__devpilotMobileProjectsCircuitBreaker" in SOURCE
    assert "event.stopImmediatePropagation()" in SOURCE
    assert "setActiveView('projects')" in SOURCE
    assert "showView('projects')" in SOURCE


def test_mobile_projects_use_ultralight_api_page():
    assert "const MOBILE_PROJECT_LIMIT = 6" in SOURCE
    assert "const MOBILE_PROJECT_TIMEOUT_MS = 7000" in SOURCE
    assert "/api/ui/projects?limit=${MOBILE_PROJECT_LIMIT}" in SOURCE
    assert "new AbortController()" in SOURCE
    assert "Projetos demoraram mais de 7 segundos" in SOURCE


def test_mobile_projects_do_not_render_heavy_visuals():
    assert "devpilot-mobile-project-safe" in SOURCE
    assert ".project-ship-svg" in SOURCE
    assert ".project-ship-hangar" in SOURCE
    assert "#projects-view canvas" in SOURCE
    assert "#projects-view svg" in SOURCE


def test_project_actions_remain_available_in_safe_mode():
    assert "data-mobile-project-analyze" in SOURCE
    assert "data-mobile-project-task" in SOURCE
    assert "__devpilotLoadFeature?.('taskModal')" in SOURCE
