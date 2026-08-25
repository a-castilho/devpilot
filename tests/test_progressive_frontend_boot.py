from pathlib import Path

from app.main import (
    STATIC,
    _CORE_AUTHENTICATED_SCRIPTS,
    _DEFERRED_AUTHENTICATED_SCRIPTS,
    spa,
)


def test_spa_does_not_restore_deprecated_feature_policy():
    response = spa("")
    assert response.headers.get("permissions-policy") == "microphone=(self)"
    assert "feature-policy" not in response.headers


def test_initial_html_contains_only_preauth_scripts_plus_inline_boot():
    html = spa("").body.decode("utf-8")
    assert '<script src="/assets/acs-loader.js?v=' in html
    assert '<script src="/assets/auth-ui.js?v=' in html
    assert '<script src="/assets/app.js?v=' not in html
    assert '<script src="/assets/feature-loader.js?v=' not in html
    assert 'window.__devpilotBoot' in html
    assert 'requestIdleCallback' not in html
    assert 'deferredSources' not in html


def test_authenticated_core_is_minimal_and_optional_inventory_remains_available():
    assert _CORE_AUTHENTICATED_SCRIPTS == ["app.js", "feature-loader.js"]

    # Paginação de tarefas agora pertence ao app.js e não pode voltar como
    # módulo automático/deferred do pós-login.
    assert "tasks-lazy-load.js" not in _CORE_AUTHENTICATED_SCRIPTS
    assert "tasks-lazy-load.js" not in _DEFERRED_AUTHENTICATED_SCRIPTS

    # Módulos realmente opcionais continuam apenas como inventário; o navegador
    # não percorre essa lista durante autenticação.
    assert "telemetry-capture.js" in _DEFERRED_AUTHENTICATED_SCRIPTS
    assert "telemetry-replay-capture.js" in _DEFERRED_AUTHENTICATED_SCRIPTS


def test_auth_requires_explicit_resume_before_runtime():
    source = Path(STATIC / "auth-ui.js").read_text(encoding="utf-8")
    assert "window.__devpilotAuthReady = new Promise" in source
    assert "Continuar sessão" in source
    assert "renderResumeSession(token)" in source
    assert "async function validateToken(token)" in source
    assert "fetchWithTimeout('/api/auth/me'" in source
    assert "Authorization: `Bearer ${token}`" in source
    assert "completeAuth(true)" in source


def test_acs_loader_is_not_a_runtime_guard_anymore():
    source = Path(STATIC / "acs-loader.js").read_text(encoding="utf-8")
    assert "MutationObserver" not in source
    assert "body.appendChild =" not in source
    assert "SAFE_AUTH_BOOT_SCRIPTS" not in source
