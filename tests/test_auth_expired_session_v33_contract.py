from pathlib import Path


AUTH_UI = Path("app/static/auth-ui.js")
ACS_LOADER = Path("app/static/acs-loader.js")
TASK_MODAL = Path("app/static/task-modal.js")


def test_expired_token_is_cleared_before_resume_session():
    auth = AUTH_UI.read_text(encoding="utf-8")
    loader = ACS_LOADER.read_text(encoding="utf-8")

    assert "function tokenExpired(token)" in auth
    assert "if (!token || tokenExpired(token))" in auth
    assert "renderLoginForm(consumeAuthMessage('Sua sessão expirou. Entre novamente.'))" in auth

    assert "function tokenExpired(token)" in loader
    assert "localStorage.removeItem(TOKEN_KEY)" in loader
    assert "devpilotExpiredSessionCleared" in loader


def test_execution_submit_forces_fresh_login_on_401():
    source = TASK_MODAL.read_text(encoding="utf-8")

    assert "function requireFreshLogin(" in source
    assert "if (!token || tokenExpired(token))" in source
    assert "if (response.status === 401)" in source
    assert "localStorage.removeItem('devpilot-token')" in source
    assert "sessionStorage.setItem('devpilot-auth-message'" in source
    assert "window.location.reload()" in source


def test_auth_message_is_one_shot_after_reload():
    auth = AUTH_UI.read_text(encoding="utf-8")

    assert "function consumeAuthMessage(" in auth
    assert "sessionStorage.removeItem(AUTH_MESSAGE_KEY)" in auth
    assert "sessionStorage.removeItem(AUTH_MESSAGE_KEY);" in auth
