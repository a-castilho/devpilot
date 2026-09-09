from pathlib import Path

MENU = Path("app/static/mobile-accordion-menu.js")
BACK = Path("app/static/mobile-page-back.js")


def test_mobile_shell_loads_standard_top_back_runtime():
    menu = MENU.read_text(encoding="utf-8")
    assert "ensureMobilePageBackRuntime" in menu
    assert "mobile-page-back.js" in menu
    assert "data-mobile-page-back" in menu


def test_standard_back_is_first_control_on_internal_mobile_views():
    source = BACK.read_text(encoding="utf-8")
    assert "view.prepend(button)" in source
    assert "view.id === 'overview-view'" in source
    assert "view.id === 'new-project-view'" in source
    assert "return 'projects'" in source
    assert "return 'overview'" in source
    assert "position: sticky" in source
    assert "min-height: 44px" in source
    assert "body.mobile-route #tasks-v9-back" in source
    assert "body.mobile-route .project-builder-back" in source


def test_standard_back_uses_existing_navigation_instead_of_reloading_spa():
    source = BACK.read_text(encoding="utf-8")
    assert ".nav[data-view=" in source
    assert "button.click()" in source
    assert "devpilot:view-changed" in source
