from pathlib import Path


NAV_CSS = Path("app/static/simplified-nav.css")
NAV_JS = Path("app/static/simplified-nav.js")


def test_desktop_sidebar_can_collapse_and_restore_persisted_state():
    script = NAV_JS.read_text(encoding="utf-8")

    assert "devpilot-sidebar-collapsed" in script
    assert "sidebar-collapse-toggle" in script
    assert "setSidebarCollapsed" in script
    assert "localStorage.setItem(SIDEBAR_COLLAPSED_KEY" in script
    assert "matchMedia('(min-width: 901px)')" in script
    assert "Expandir menu lateral" in script
    assert "Recolher menu lateral" in script


def test_collapsed_sidebar_keeps_icon_navigation_and_mobile_hides_toggle():
    css = NAV_CSS.read_text(encoding="utf-8")

    assert "html.sidebar-collapsed .shell" in css
    assert "grid-template-columns: 72px minmax(0, 1fr)" in css
    assert "html.sidebar-collapsed .sidebar > nav > .nav::before" in css
    assert "@media (max-width: 900px)" in css
    assert ".sidebar-collapse-toggle" in css
    assert "display: none !important" in css


def test_layout_completion_adds_accessible_focus_and_touch_targets():
    css = NAV_CSS.read_text(encoding="utf-8")

    assert "button:focus-visible" in css
    assert "outline: 2px solid var(--cyan)" in css
    assert "min-height: 44px" in css
    assert "-webkit-tap-highlight-color: transparent" in css


def test_small_mobile_uses_one_metric_card_per_row():
    css = NAV_CSS.read_text(encoding="utf-8")

    mobile = css.split("@media (max-width: 520px)", 1)[1]
    assert ".metrics" in mobile
    assert "grid-template-columns: minmax(0, 1fr)" in mobile
