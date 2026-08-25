from pathlib import Path


CSS = Path("app/static/mobile-route.css")
MENU = Path("app/static/mobile-accordion-menu.js")


def test_mobile_route_has_readable_fallback_labels():
    css = CSS.read_text(encoding="utf-8")
    assert ".sidebar:not(:has(.mobile-simple-nav)) nav .nav" in css
    assert "font-size: 9px !important" in css
    assert "white-space: nowrap !important" in css


def test_simple_mobile_menu_keeps_explicit_labels():
    js = MENU.read_text(encoding="utf-8")
    for label in ("Início", "Projetos", "Tarefas", "Menu"):
        assert f"<small>{label}</small>" in js
    assert "body.mobile-route .mobile-simple-item > small" in js
    assert "display: block !important" in js
