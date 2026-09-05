from pathlib import Path


AUTH_UI = Path("app/static/auth-ui.js")


def test_successful_login_hands_off_without_reload():
    source = AUTH_UI.read_text(encoding="utf-8")
    submit_block = source.split("form?.addEventListener('submit'", 1)[1].split("function renderResumeSession", 1)[0]
    handoff_block = source.split("function handoffAuthenticatedRuntime", 1)[1].split("async function readStatus", 1)[0]

    assert "localStorage.setItem(TOKEN_KEY, data.access_token)" in submit_block
    assert "document.dispatchEvent(new CustomEvent('devpilot:login-complete'))" in submit_block
    assert "handoffAuthenticatedRuntime(errorBox)" in submit_block
    assert "installLogout()" in handoff_block
    assert "revealDashboard()" in handoff_block
    assert "completeAuth(true)" in handoff_block
    assert "sessionStorage.setItem(TOKEN_KEY" not in submit_block
    assert "sessionStorage.getItem(TOKEN_KEY" not in submit_block
    assert "sessionStorage.removeItem(AUTH_MESSAGE_KEY)" in submit_block
    assert "location.reload()" not in submit_block


def test_login_ready_promise_is_resolved_by_same_page_handoff():
    source = AUTH_UI.read_text(encoding="utf-8")

    assert "window.__devpilotAuthReady = new Promise" in source
    assert "const completeAuth = value =>" in source
    assert "resolve(Boolean(value))" in source
    assert "completeAuth(true)" in source
    assert "resumeFreshLogin" not in source
    assert "devpilot-fresh-login" not in source


def test_saved_session_still_requires_explicit_resume():
    source = AUTH_UI.read_text(encoding="utf-8")
    resume_block = source.split("function renderResumeSession(token)", 1)[1].split("const boot = async", 1)[0]

    assert "renderResumeSession(token)" in source
    assert "Continuar sessão" in source
    assert "await validateToken(token)" in resume_block
    assert "handoffAuthenticatedRuntime(errorBox)" in resume_block


def test_reload_is_reserved_for_explicit_logout():
    source = AUTH_UI.read_text(encoding="utf-8")
    logout_block = source.split("const installLogout = () =>", 1)[1].split("function handoffAuthenticatedRuntime", 1)[0]

    assert "localStorage.removeItem(TOKEN_KEY)" in logout_block
    assert "location.reload()" in logout_block
