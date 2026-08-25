from pathlib import Path


AUTH_UI = Path("app/static/auth-ui.js")


def test_successful_login_restarts_with_fresh_session_marker():
    source = AUTH_UI.read_text(encoding="utf-8")
    assert "const FRESH_LOGIN_KEY = 'devpilot-fresh-login'" in source
    assert "sessionStorage.setItem(FRESH_LOGIN_KEY, '1')" in source
    assert "location.reload()" in source


def test_fresh_login_validates_once_and_completes_auth():
    source = AUTH_UI.read_text(encoding="utf-8")
    assert "async function resumeFreshLogin(token)" in source
    assert "await validateToken(token)" in source
    assert "completeAuth(true)" in source
    assert "sessionStorage.removeItem(FRESH_LOGIN_KEY)" in source


def test_saved_session_still_requires_explicit_resume():
    source = AUTH_UI.read_text(encoding="utf-8")
    assert "renderResumeSession(token)" in source
    assert "Continuar sessão" in source
