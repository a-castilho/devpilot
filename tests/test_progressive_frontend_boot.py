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


def test_initial_html_does_not_execute_dashboard_bundle_directly():
    html = spa("").body.decode("utf-8")
    assert '<script src="/assets/acs-loader.js?v=' in html
    assert '<script src="/assets/auth-ui.js?v=' in html
    assert '<script src="/assets/app.js?v=' not in html
    assert 'window.__devpilotBoot' in html
    assert 'requestIdleCallback' in html


def test_task_limiter_is_core_and_telemetry_is_deferred():
    assert _CORE_AUTHENTICATED_SCRIPTS[0] == "app.js"
    assert "tasks-lazy-load.js" in _CORE_AUTHENTICATED_SCRIPTS
    assert "telemetry-capture.js" in _DEFERRED_AUTHENTICATED_SCRIPTS
    assert "telemetry-replay-capture.js" in _DEFERRED_AUTHENTICATED_SCRIPTS


def test_auth_validates_session_before_runtime():
    source = Path(STATIC / "auth-ui.js").read_text(encoding="utf-8")
    assert "window.__devpilotAuthReady = validateStoredSession()" in source
    assert "fetch('/api/auth/me'" in source


def test_workspace_skin_has_no_global_dom_observer():
    source = Path(STATIC / "workspace-skins.js").read_text(encoding="utf-8")
    assert "MutationObserver" not in source
