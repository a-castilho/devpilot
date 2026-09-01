from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = (ROOT / "app/static/page-navigation-v26.js").read_text(encoding="utf-8")
DELIVERY = (ROOT / "app/static/product-delivery-ui.js").read_text(encoding="utf-8")
APP = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_navigation_does_not_kill_feature_loader_clicks():
    assert "event.stopImmediatePropagation();\n    navigate(viewName" not in NAV
    assert "document.addEventListener('click'" in NAV
    assert "FEATURE_BY_VIEW" in NAV
    assert "await window.__devpilotLoadFeature(feature)" in NAV


def test_executions_navigation_is_mapped_and_loadable():
    assert "tasks: 'Execuções'" in NAV
    assert "tasks: 'tasks'" in NAV
    assert "['.nav[data-view=\"tasks\"]', 'tasks']" in LOADER
    assert "if (name === 'tasks')" in APP
    assert "loadAllTasks" in APP


def test_dynamic_project_actions_remain_delegated():
    assert "installDelegatedClicks" in DELIVERY
    assert "document.addEventListener('click'" in DELIVERY
    assert "data-delivery-history" in DELIVERY
    assert "data-delivery-action" in DELIVERY
    assert "data-project-create-sticky" in DELIVERY
    assert "hostObserver.observe(host, {childList:true});" in DELIVERY
    assert "subtree:true" not in DELIVERY


def test_project_execution_and_analysis_controls_exist_in_native_renderer():
    assert "data-project-task" in APP
    assert "class=\"link analyze\"" in APP
    assert "devpilotOpenTaskModal" in APP
    assert "/analyze" in APP
