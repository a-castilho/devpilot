from pathlib import Path


DASHBOARD_CSS = Path("app/static/dashboard-layout-v2.css")
MOBILE_MENU_CSS = Path("app/static/mobile-accordion-menu.css")


def test_dashboard_v2_is_loaded_after_existing_layout_layers():
    mobile_css = MOBILE_MENU_CSS.read_text(encoding="utf-8")

    assert mobile_css.startswith("@import url('/assets/dashboard-layout-v2.css?v=20260829-1');")


def test_dashboard_v2_uses_live_existing_dom_without_fake_metric_markup():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "#overview-view" in css
    assert ".metrics" in css
    assert ".grid-two" in css
    assert ".panel" in css
    assert "dashboard-accent" in css


def test_dashboard_v2_is_responsive_from_desktop_to_small_mobile():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in css
    assert "@media (max-width: 1180px)" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css
    assert "@media (max-width: 520px)" in css
    assert "grid-template-columns: minmax(0, 1fr)" in css


def test_dashboard_v2_preserves_accessible_reduced_motion_behavior():
    css = DASHBOARD_CSS.read_text(encoding="utf-8")

    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition: none !important" in css
