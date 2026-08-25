from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app" / "static" / "mobile-accordion-menu.js"
CSS = ROOT / "app" / "static" / "mobile-accordion-menu.css"
INDEX = ROOT / "app" / "static" / "index.html"


def test_response_manager_is_loaded_with_mobile_shell():
    html = INDEX.read_text(encoding="utf-8")
    assert "mobile-accordion-menu.js" in html
    assert "mobile-accordion-menu.css" in html


def test_response_manager_exposes_status_types_and_form_feedback():
    js = JS.read_text(encoding="utf-8")
    assert "window.DevPilotResponses" in js
    for response_type in ("success", "error", "warning", "info", "loading"):
        assert response_type in js
    for form_id in (
        "organization-form",
        "project-form",
        "project-builder-form",
        "task-form",
        "provider-form",
    ):
        assert form_id in js
    assert "Conectando organização e preparando a sincronização" in js
    assert "A operação está demorando mais que o esperado" in js


def test_response_manager_is_accessible_and_bounded():
    js = JS.read_text(encoding="utf-8")
    assert "aria-live" in js
    assert "role', type === 'error' || type === 'warning' ? 'alert' : 'status'" in js
    assert "while (stack.children.length > 4)" in js
    assert "aria-label=\"Fechar aviso\"" in js


def test_response_balloons_have_mobile_safe_area_rules():
    css = CSS.read_text(encoding="utf-8")
    assert ".dp-response-stack" in css
    assert "env(safe-area-inset-top)" in css
    assert "@media (max-width: 900px)" in css
    assert ".dp-response-balloon" in css
