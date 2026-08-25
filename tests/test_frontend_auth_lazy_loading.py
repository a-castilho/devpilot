from pathlib import Path

from app.main import (
    _CORE_AUTHENTICATED_SCRIPTS,
    _DEFERRED_AUTHENTICATED_SCRIPTS,
    _authenticated_script_loader,
    _strip_pre_auth_heavy_scripts,
    spa,
)

AUTH_UI = Path("app/static/auth-ui.js")
APP_JS = Path("app/static/app.js")


def test_pre_auth_html_keeps_only_auth_script():
    html = """
    <body>
      <script src="/assets/app.js" defer></script>
      <script src="/assets/auth-ui.js" defer></script>
      <script src="/assets/project-ships.js?v=1" defer></script>
    </body>
    """
    result = _strip_pre_auth_heavy_scripts(html)
    assert '/assets/auth-ui.js' in result
    assert '/assets/app.js' not in result
    assert '/assets/project-ships.js' not in result


def test_authenticated_loader_validates_session_before_core():
    loader = _authenticated_script_loader()
    assert "window.__devpilotAuthReady" in loader
    assert "fetch('/api/auth/me'" in loader
    assert "boot.phase = 'auth'" in loader
    assert "boot.phase = 'waiting-login'" in loader
    assert "const authenticated = await validateSession()" in loader
    assert "script.async = false" in loader
    assert "await nextPaint()" in loader
    assert "requestIdleCallback" in loader
    assert "await whenIdle()" in loader
    assert "devpilot:authenticated-core-ready" in loader
    assert "devpilot:authenticated-ui-ready" in loader


def test_authenticated_boot_lists_are_small_core_and_deduplicated():
    scripts = [*_CORE_AUTHENTICATED_SCRIPTS, *_DEFERRED_AUTHENTICATED_SCRIPTS]
    assert len(_CORE_AUTHENTICATED_SCRIPTS) <= 7
    assert len(scripts) == len(set(scripts))
    assert _CORE_AUTHENTICATED_SCRIPTS[0] == "app.js"
    assert "profile.js" in _CORE_AUTHENTICATED_SCRIPTS
    assert "simplified-nav.js" in _CORE_AUTHENTICATED_SCRIPTS
    assert "project-provisioning.js" in _DEFERRED_AUTHENTICATED_SCRIPTS
    assert "build-game-cockpit.js" in _DEFERRED_AUTHENTICATED_SCRIPTS


def test_loader_does_not_relaunch_acs_loader_or_duplicate_project_ships():
    loader = _authenticated_script_loader()
    scripts = [*_CORE_AUTHENTICATED_SCRIPTS, *_DEFERRED_AUTHENTICATED_SCRIPTS]
    assert "acs-loader.js" not in scripts
    assert scripts.count("project-ships.js") == 1
    assert 'data-project-ships-loader="1"' in loader
    assert "managedBy" in loader


def test_auth_ui_handles_expired_session_before_dashboard_boot():
    source = AUTH_UI.read_text(encoding="utf-8")
    assert "window.__devpilotAuthReady = validateStoredSession()" in source
    assert "fetch('/api/auth/me'" in source
    assert "Sua sessão expirou. Entre novamente." in source
    assert "if (!modal.open) modal.showModal()" in source


def test_task_approve_selector_uses_collection_without_global_dom_patch():
    app_source = APP_JS.read_text(encoding="utf-8")
    auth_source = AUTH_UI.read_text(encoding="utf-8")
    assert ";$$('.approve').forEach" in app_source
    assert ";$('.approve').forEach" not in app_source
    assert "document.querySelector = selector" not in auth_source


def test_spa_keeps_app_js_behind_authenticated_loader():
    response = spa("")
    html = response.body.decode("utf-8")
    assert '<script src="/assets/auth-ui.js?v=' in html
    assert '<script src="/assets/app.js?v=' not in html
    assert '<script src="/assets/build-game-cockpit.js' not in html
    assert '"/assets/app.js?v=' in html
    assert "window.__devpilotAuthReady" in html
    assert "window.__devpilotBoot" in html


def test_app_runtime_does_not_require_removed_legacy_login_button():
    source = APP_JS.read_text(encoding="utf-8")
    assert "const legacyTokenSubmit=$('#save-token')" in source
    assert "if(legacyTokenSubmit)legacyTokenSubmit.onclick" in source
    assert "$('#save-token').onclick" not in source


def test_unauthorized_api_clears_stale_session_and_reopens_login():
    source = APP_JS.read_text(encoding="utf-8")
    assert "localStorage.removeItem('devpilot-token')" in source
    assert "openAuthModal()" in source


def test_direct_index_route_uses_safe_authenticated_shell():
    response = spa("index.html")
    html = response.body.decode("utf-8")
    assert '<script src="/assets/auth-ui.js?v=' in html
    assert '<script src="/assets/app.js?v=' not in html
    assert '"/assets/app.js?v=' in html
    assert "window.__devpilotAuthReady" in html
