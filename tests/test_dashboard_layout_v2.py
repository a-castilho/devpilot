from pathlib import Path


DASHBOARD_CSS = Path("app/static/dashboard-layout-v2.css")
MOBILE_MENU_CSS = Path("app/static/mobile-accordion-menu.css")


def test_dashboard_v2_is_loaded_from_existing_layout_stack():
    mobile_css = MOBILE_MENU_CSS.read_text(encoding="utf-8")

    assert mobile_css.startswith("@import url('/assets/dashboard-layout-v2.css?v=20260829-1');")


def test_dashboard_v2_normalizes_all_primary_surface_types():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    for selector in (
        ".view",
        ".cards",
        ".panel",
        ".project-card",
        ".builder-card",
        ".table-wrap",
        ".reports-grid",
        ".task-analytics",
    ):
        assert selector in css
    assert "--dashboard-content:1600px" in css
    assert "overflow-x:auto" in css


def test_tablet_sidebar_cannot_remain_collapsed_and_squeeze_content():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "@media (min-width:901px) and (max-width:1180px)" in css
    assert "html.sidebar-collapsed .shell" in css
    assert "grid-template-columns:220px minmax(0,1fr)!important" in css
    assert "html.sidebar-collapsed .sidebar" in css
    assert "width:220px!important" in css
    assert "html.sidebar-collapsed .brand>span:last-child" in css
    assert "display:block!important" in css


def test_dashboard_v2_is_responsive_from_desktop_to_small_mobile():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "grid-template-columns:repeat(4,minmax(0,1fr))" in css
    assert "@media (max-width:900px)" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in css
    assert "@media (max-width:560px)" in css
    assert ".metrics{grid-template-columns:1fr}" in css
    assert ".project-builder{display:block!important}" in css
    assert "dialog,.modal{width:min(96vw,620px)!important" in css


def test_dashboard_v2_preserves_accessibility_and_readability():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "body{background:var(--dashboard-bg);color:var(--dashboard-text);font-size:14px" in css
    assert "pre{overflow:auto;white-space:pre-wrap" in css
    assert "@media (prefers-reduced-motion:reduce)" in css
    assert "transition:none!important" in css
