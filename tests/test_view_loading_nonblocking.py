from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = (ROOT / "app/static/page-navigation-v26.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/page-navigation-v26.css").read_text(encoding="utf-8")
VIEWPORT = (ROOT / "app/static/viewport-adaptive-v15.js").read_text(encoding="utf-8")


def test_view_is_committed_before_lazy_feature_loading():
    navigate = NAV.split("async function navigate", 1)[1]
    assert navigate.index("commitView(viewName, options)") < navigate.index("await ensureFeature(viewName)")


def test_new_project_is_an_explicit_lazy_view():
    assert "'new-project': 'projectBuilder'" in NAV
    assert 'html[data-devpilot-view="new-project"] #new-project-view' in CSS


def test_switching_state_never_blocks_entire_main():
    assert "html.dp-page-switching main {\n  pointer-events: auto;" in CSS
    assert "html.dp-page-switching main {\n  pointer-events: none;" not in CSS


def test_switching_state_is_cleared_even_after_lazy_failure():
    navigate = NAV.split("async function navigate", 1)[1]
    assert "finally" in navigate
    assert "finish(viewName, options, epoch, ready)" in navigate
    assert "root.classList.remove('dp-page-switching')" in NAV


def test_navigation_css_cache_is_busted_for_mobile_clients():
    assert "/assets/page-navigation-v26.css?v=20260903-viewfix1" in VIEWPORT
