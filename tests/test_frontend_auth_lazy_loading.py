from app.main import (
    _CORE_AUTHENTICATED_SCRIPTS,
    _DEFERRED_AUTHENTICATED_SCRIPTS,
    _ON_DEMAND_CHAT_SCRIPTS,
    _authenticated_script_loader,
    _strip_pre_auth_heavy_scripts,
    spa,
)


def test_pre_auth_html_keeps_only_boot_scripts():
    html = """
    <body>
      <script src="/assets/app.js" defer></script>
      <script src="/assets/project-ships.js?v=1" defer></script>
      <script src="/assets/build-game-cockpit.js?v=1" defer></script>
    </body>
    """
    result = _strip_pre_auth_heavy_scripts(html)
    assert '/assets/app.js' in result
    assert '/assets/project-ships.js' not in result
    assert '/assets/build-game-cockpit.js' not in result


def test_authenticated_loader_yields_between_core_modules_and_uses_idle_time_for_features():
    loader = _authenticated_script_loader()
    assert "localStorage.getItem('devpilot-token')" in loader
    assert "script.async = false" in loader
    assert "await nextPaint()" in loader
    assert "requestIdleCallback" in loader
    assert "await whenIdle()" in loader
    assert "await sleep(90)" in loader
    assert "devpilot:authenticated-core-ready" in loader
    assert "devpilot:authenticated-ui-ready" in loader


def test_authenticated_boot_lists_are_small_core_and_deduplicated():
    scripts = [*_CORE_AUTHENTICATED_SCRIPTS, *_DEFERRED_AUTHENTICATED_SCRIPTS]
    assert len(_CORE_AUTHENTICATED_SCRIPTS) <= 6
    assert len(scripts) == len(set(scripts))
    assert "profile.js" in _CORE_AUTHENTICATED_SCRIPTS
    assert "simplified-nav.js" in _CORE_AUTHENTICATED_SCRIPTS
    assert "project-provisioning.js" in _DEFERRED_AUTHENTICATED_SCRIPTS
    assert "build-game-cockpit.js" in _DEFERRED_AUTHENTICATED_SCRIPTS
    assert "mission-control.js" in _DEFERRED_AUTHENTICATED_SCRIPTS


def test_chat_voice_modules_stay_off_until_user_opens_chat():
    loader = _authenticated_script_loader()
    boot_scripts = set(_CORE_AUTHENTICATED_SCRIPTS) | set(_DEFERRED_AUTHENTICATED_SCRIPTS)

    assert set(_ON_DEMAND_CHAT_SCRIPTS).isdisjoint(boot_scripts)
    assert len(_ON_DEMAND_CHAT_SCRIPTS) == len(set(_ON_DEMAND_CHAT_SCRIPTS))
    assert "voice-enhanced-ui.js" in _ON_DEMAND_CHAT_SCRIPTS
    assert "voice-chatgpt-layout.js" in _ON_DEMAND_CHAT_SCRIPTS
    assert "super-admin-voice.js" in _ON_DEMAND_CHAT_SCRIPTS
    assert "window.devpilotLoadChat = loadChat" in loader
    assert "#voice-hero, #voice-dock" in loader
    assert "devpilot:chat-open-requested" in loader
    assert "devpilot:chat-ui-ready" in loader

    start_section = loader.split("const start = async () =>", 1)[1]
    assert "loadChat()" not in start_section


def test_loader_does_not_relaunch_acs_loader_or_duplicate_project_ships():
    loader = _authenticated_script_loader()
    scripts = [*_CORE_AUTHENTICATED_SCRIPTS, *_DEFERRED_AUTHENTICATED_SCRIPTS]
    assert "acs-loader.js" not in scripts
    assert scripts.count("project-ships.js") == 1
    assert 'data-project-ships-loader="1"' in loader
    assert "managedBy" in loader


def test_spa_does_not_boot_heavy_scripts_before_authentication():
    response = spa("")
    html = response.body.decode("utf-8")
    assert '<script src="/assets/app.js?v=' in html
    assert '<script src="/assets/auth-ui.js?v=' in html
    assert '<script src="/assets/build-game-cockpit.js' not in html
    assert '<script src="/assets/project-ships.js' not in html
    assert "localStorage.getItem('devpilot-token')" in html
    assert "window.__devpilotBoot" in html