from pathlib import Path

MENU = Path("app/static/mobile-accordion-menu.js")


def test_standard_back_is_owned_by_mobile_shell_without_dynamic_script_loader():
    source = MENU.read_text(encoding="utf-8")
    assert "const BACK_CLASS = 'mobile-page-back'" in source
    assert "ensureBackStyle" in source
    assert "view.prepend(button)" in source
    assert "document.createElement('script')" not in source
    assert "mobile-page-back.js" not in source


def test_standard_back_is_first_control_and_stays_pinned_on_internal_mobile_views():
    source = MENU.read_text(encoding="utf-8")
    assert "view.id === 'overview-view'" in source
    assert "view?.id === 'new-project-view'" in source
    assert "return 'projects'" in source
    assert "return 'overview'" in source
    assert "position: sticky" in source
    assert "top: max(8px, env(safe-area-inset-top))" in source
    assert "width:100%" in source
    assert "min-height:56px" in source
    assert "body.mobile-route #tasks-v9-back" in source
    assert "body.mobile-route .project-builder-back" in source


def test_internal_mobile_view_opens_at_top_and_uses_existing_spa_navigation():
    source = MENU.read_text(encoding="utf-8")
    assert "scheduleBack({scrollToTop: true})" in source
    assert "window.scrollTo({top: 0" in source
    assert "document.scrollingElement?.scrollTo?.({top: 0" in source
    assert "view.scrollTo?.({top: 0" in source
    assert ".nav[data-view=" in source
    assert "button.click()" in source
    assert "devpilot:view-changed" in source
