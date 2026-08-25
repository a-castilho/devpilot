from pathlib import Path


AUTH_JS = Path("app/static/auth-ui.js")


def test_auth_status_has_timeout_guard():
    js = AUTH_JS.read_text(encoding="utf-8")
    assert "FETCH_TIMEOUT_MS" in js
    assert "AbortController" in js
    assert "fetchWithTimeout('/api/auth/status'" in js


def test_auth_boot_never_waits_forever_on_blank_screen():
    js = AUTH_JS.read_text(encoding="utf-8")
    assert "Nunca deixe o mobile em uma tela preta" in js
    assert "root.classList.contains('devpilot-auth-pending')" in js
    assert "renderResumeSession(token)" in js
    assert "renderLoginForm('Não foi possível consultar o status do servidor.')" in js


def test_saved_session_validation_is_bounded():
    js = AUTH_JS.read_text(encoding="utf-8")
    assert "fetchWithTimeout('/api/auth/me'" in js
    assert "O servidor demorou para responder" in js
