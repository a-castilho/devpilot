from app.main import (
    _CORE_AUTHENTICATED_SCRIPTS,
    _DEFERRED_AUTHENTICATED_SCRIPTS,
    _FEATURE_AUTHENTICATED_SCRIPTS,
    _INTERACTION_AUTHENTICATED_SCRIPTS,
    _MOBILE_SHELL_AUTHENTICATED_SCRIPTS,
    _VIEW_AUTHENTICATED_SCRIPTS,
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


def test_authenticated_loader_yields_and_loads_optional_features_on_demand():
    loader = _authenticated_script_loader()
    assert "localStorage.getItem('devpilot-token')" in loader
    assert "requestIdleCallback" in loader
    assert "await whenIdle()" in loader
    assert "await nextPaint()" in loader
    assert "const viewGroups" in loader
    assert "const featureGroups" in loader
    assert "const interactionSources" in loader
    assert "const loadView" in loader
    assert "const loadFeature" in loader
    assert "featureFromTarget" in loader
    assert "devpilot:asset-group-ready" in loader
    assert "}, 6000);" in loader
    assert "const deferredSources" not in loader


def test_authenticated_boot_inventory_is_grouped_and_deduplicated():
    scripts = [*_CORE_AUTHENTICATED_SCRIPTS, *_DEFERRED_AUTHENTICATED_SCRIPTS]
    assert len(_CORE_AUTHENTICATED_SCRIPTS) <= 6
    assert len(scripts) == len(set(scripts))
    assert "profile.js" in _CORE_AUTHENTICATED_SCRIPTS
    assert "simplified-nav.js" in _CORE_AUTHENTICATED_SCRIPTS
    assert "project-provisioning.js" in _VIEW_AUTHENTICATED_SCRIPTS["projects"]
    assert "task-analytics.js" in _VIEW_AUTHENTICATED_SCRIPTS["tasks"]
    assert "build-game-cockpit.js" in _FEATURE_AUTHENTICATED_SCRIPTS["game"]
    assert "mission-control.js" in _FEATURE_AUTHENTICATED_SCRIPTS["game"]
    assert "linux-terminal.js" in _INTERACTION_AUTHENTICATED_SCRIPTS
    assert "linux-beginner-coach.js" in _INTERACTION_AUTHENTICATED_SCRIPTS
    assert "telemetry-capture.js" in _INTERACTION_AUTHENTICATED_SCRIPTS
    assert "mobile-accordion-menu.js" in _MOBILE_SHELL_AUTHENTICATED_SCRIPTS


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
    assert "/assets/frontend-performance.css?v=" in html


def test_mobile_route_gets_lightweight_performance_guard():
    response = spa("mobile")
    html = response.body.decode("utf-8")
    assert '<body class="mobile-route">' in html
    assert "/assets/mobile-route.css?v=" in html
    assert "/assets/frontend-performance.css?v=" in html
