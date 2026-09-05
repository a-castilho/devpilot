from pathlib import Path


MENU_JS = Path("app/static/mobile-accordion-menu.js")
MENU_CSS = Path("app/static/mobile-accordion-menu.css")
RESPONSE_JS = Path("app/static/response-manager.js")
INDEX = Path("app/static/index.html")


def test_mobile_simple_menu_keeps_five_primary_actions():
    js = MENU_JS.read_text(encoding="utf-8")

    assert "mobile-simple-nav" in js
    assert 'data-simple-target="overview"' in js
    assert 'data-simple-target="projects"' in js
    assert 'data-simple-target="tasks"' in js
    assert "data-simple-game" in js
    assert "data-simple-menu-open" in js
    for label in ("Início", "Projetos", "Execuções", "Jogo", "Menu"):
        assert f"<small>{label}</small>" in js
    assert "grid-template-columns:repeat(5" in js


def test_mobile_menu_reuses_authoritative_navigation_and_permissions():
    js = MENU_JS.read_text(encoding="utf-8")

    assert "sourceNav" in js
    assert "item.hidden" in js
    assert "nav-super-admin-forbidden" in js
    assert "item.click()" in js
    assert "MutationObserver" not in js
    assert "devpilot:view-changed" in js
    assert "devpilot:feature-ready" in js


def test_mobile_menu_bootstraps_after_dom_without_polling_sidebar():
    js = MENU_JS.read_text(encoding="utf-8")

    assert "function mountMobileMenu()" in js
    assert "document.readyState === 'loading'" in js
    assert "DOMContentLoaded" in js
    assert "if (!sidebar || !sourceNav) return false" in js
    assert "if (existingRoot)" in js
    assert "bootstrapMobileMenu" not in js
    assert "waitObserver" not in js


def test_mobile_menu_is_simple_not_favorites_search_or_nested_accordion():
    js = MENU_JS.read_text(encoding="utf-8")

    for legacy_feature in (
        "devpilot-mobile-favorites-v1",
        "MAX_FAVORITES",
        "mobile-accordion-search",
        "mobile-accordion-group",
        "toggleFavorite",
    ):
        assert legacy_feature not in js


def test_mobile_menu_supports_keyboard_close_and_accessibility():
    js = MENU_JS.read_text(encoding="utf-8")

    assert "aria-modal" in js
    assert "Menu do DevPilot" in js
    assert "aria-expanded" in js
    assert "event.key === 'Escape'" in js
    assert "aria-label=\"Fechar menu\"" in js
    assert "aria-current" in js


def test_mobile_css_respects_safe_area_and_touch_targets():
    css = MENU_CSS.read_text(encoding="utf-8")

    assert "env(safe-area-inset-bottom)" in css
    assert "env(safe-area-inset-left)" in css
    assert "env(safe-area-inset-right)" in css
    assert "env(safe-area-inset-top)" in css
    assert "touch-action:manipulation" in css
    assert "body.mobile-simple-open{overflow:hidden!important}" in css


def test_response_manager_remains_standalone_from_mobile_menu():
    js = MENU_JS.read_text(encoding="utf-8")
    responses = RESPONSE_JS.read_text(encoding="utf-8")

    assert "response-manager.js" not in js
    assert "data-response-manager" not in js
    assert "document.createElement('script')" not in js
    assert "window.DevPilotResponses" in responses
    assert "aria-live" in responses
    assert "data-type=\"loading\"" in responses


def test_index_still_loads_mobile_runtime_once():
    html = INDEX.read_text(encoding="utf-8")

    assert html.count("/assets/mobile-accordion-menu.css?v=") == 1
    assert html.count("/assets/mobile-accordion-menu.js?v=") == 1
