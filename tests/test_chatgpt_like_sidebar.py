from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "app/static/simplified-nav.css").read_text(encoding="utf-8")
JS = (ROOT / "app/static/simplified-nav.js").read_text(encoding="utf-8")


def test_desktop_sidebar_uses_compact_neutral_navigation_pattern():
    assert "--devpilot-sidebar-width: 260px" in CSS
    assert "--devpilot-sidebar-bg: #171717" in CSS
    assert "--devpilot-sidebar-hover: #212121" in CSS
    assert "--devpilot-sidebar-active: #2f2f2f" in CSS
    assert ".sidebar > nav" in CSS
    assert "overflow-y: auto" in CSS
    assert ".system-card:hover" in CSS


def test_sidebar_keeps_search_groups_and_dynamic_navigation_support():
    assert "Buscar no DevPilot" in JS
    assert "groupState" in JS
    assert "MutationObserver" in JS
    assert "data-nav-group" in CSS
    assert "nav-group-collapsed-item" in CSS


def test_sidebar_keeps_keyboard_and_focus_accessibility():
    assert "event.key === 'Enter'" in JS
    assert "event.key === 'Escape'" in JS
    assert ":focus-visible" in CSS
