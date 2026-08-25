from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_persisted_session_requires_explicit_resume():
    auth = read("app/static/auth-ui.js")

    assert "Continuar sessão" in auth
    assert "dashboard só será iniciado depois da sua confirmação" in auth
    assert "window.__devpilotAuthReady = new Promise" in auth
    assert "renderResumeSession(token)" in auth
    assert "sessionStorage.getItem(EXPLICIT_LOGIN_KEY)" in auth


def test_auth_does_not_override_document_query_selector():
    auth = read("app/static/auth-ui.js")

    assert "document.querySelector =" not in auth
    assert "nativeQuerySelector" not in auth


def test_core_app_uses_real_multi_selector_for_approval_buttons():
    app = read("app/static/app.js")

    assert "$$('.approve').forEach" in app
    assert "$('.approve').forEach" not in app


def test_core_app_has_no_legacy_save_token_click_binding():
    app = read("app/static/app.js")

    assert "$('#save-token').onclick" not in app
    assert "$('#token').value" not in app


def test_mobile_navigation_has_no_attribute_mutation_observer_loop():
    app = read("app/static/app.js")

    assert "new MutationObserver(sync).observe(nav" not in app
    assert "attributeFilter: ['class', 'hidden', 'style']" not in app
