from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_invalid_credentials_have_prominent_accessible_feedback():
    source = (STATIC_DIR / "auth-ui.js").read_text(encoding="utf-8")

    assert 'class="auth-feedback"' in source
    assert 'role="alert"' in source
    assert 'aria-live="assertive"' in source
    assert "Credenciais inválidas. Confira os dados e tente novamente." in source
    assert "aria-invalid" in source


def test_invalid_technical_token_clears_stale_session_and_notifies_auth_form():
    source = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "localStorage.removeItem('devpilot-token')" in source
    assert "devpilot:auth-error" in source
    assert "Sua sessão expirou ou o token técnico é inválido. Entre novamente." in source
