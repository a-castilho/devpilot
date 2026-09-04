from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = (ROOT / "app/static/page-navigation-v26.js").read_text(encoding="utf-8")
FEATURE = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
APP = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MOBILE = (ROOT / "app/static/mobile-project-card-compact.js").read_text(encoding="utf-8")


def test_core_projects_path_is_heavy_without_mobile_guard():
    assert "api('/ui/projects?limit=50')" in APP


def test_mobile_projects_intercepts_before_native_show_view():
    block = NAV.split("window.showView = function devpilotVisibilitySafeShowView", 1)[1]
    assert "if (isMobileProjects(viewName))" in block
    assert "loadMobileProjectsAfterFeature()" in block
    assert "nativeShowView.apply" in block
    assert block.index("if (isMobileProjects(viewName))") < block.index("nativeShowView.apply")


def test_mobile_projects_loads_feature_before_project_request():
    block = NAV.split("async function loadMobileProjectsAfterFeature", 1)[1].split("function runNativeView", 1)[0]
    assert "await ensureFeature('projects')" in block
    assert "await window.loadProjects()" in block
    assert block.index("await ensureFeature('projects')") < block.index("await window.loadProjects()")


def test_feature_loader_never_uses_heavy_show_view_during_mobile_startup_race():
    block = FEATURE.split("async function navigateDirect", 1)[1].split("function openTaskDirect", 1)[0]
    assert "const mobileProjectsFallback" in block
    assert "viewName === 'projects'" in block
    assert "typeof window.devpilotNavigate !== 'function'" in block
    assert "else if (mobileProjectsFallback)" in block
    assert "deferredMobileProjectsLoad = true" in block
    assert "else if (typeof showView === 'function')" in block
    assert block.index("else if (mobileProjectsFallback)") < block.index("else if (typeof showView === 'function')")


def test_feature_loader_hydrates_mobile_guard_before_requesting_projects():
    block = FEATURE.split("async function navigateDirect", 1)[1].split("function openTaskDirect", 1)[0]
    assert "loadFeature(feature, {intentEpoch})" in block
    assert "deferredMobileProjectsLoad && typeof window.loadProjects === 'function'" in block
    assert "Promise.resolve(window.loadProjects())" in block
    assert block.index("loadFeature(feature, {intentEpoch})") < block.index("Promise.resolve(window.loadProjects())")


def test_mobile_project_guard_limits_initial_fetch():
    assert "const fetchLimit = () => lowPower() ? 12 : 50;" in MOBILE
    assert "api(`/ui/projects?limit=${fetchLimit()}`" in MOBILE
