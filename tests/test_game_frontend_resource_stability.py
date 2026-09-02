from pathlib import Path


GAME_SHELL_JS = Path("app/static/game-shell.js")
GAME_COCKPIT_JS = Path("app/static/build-game-cockpit.js")
MOBILE_MENU_JS = Path("app/static/mobile-accordion-menu.js")
FEATURE_LOADER_JS = Path("app/static/feature-loader.js")
GAME_HTML = Path("app/static/game/index.html")


def test_game_shell_does_not_poll_for_loader_readiness():
    source = GAME_SHELL_JS.read_text(encoding="utf-8")
    assert "setInterval(" not in source
    assert "loaderGuardTimer" not in source
    assert "startLoaderGuard" not in source
    assert "devpilot:feature-ready" in source
    assert "guardLoaderDuringBundleBoot();" in source


def test_game_shell_deduplicates_concurrent_base_loads():
    source = GAME_SHELL_JS.read_text(encoding="utf-8")
    assert "let loadInFlight = null" in source
    assert "if (loadInFlight)" in source
    assert "METRICS.dedupedLoads += 1" in source
    assert "loadInFlight = null" in source


def test_game_shell_boot_is_idempotent():
    source = GAME_SHELL_JS.read_text(encoding="utf-8")
    assert "if (window.__devpilotGameShellReady) return" in source
    assert "window.__devpilotGameShellReady = true" in source
    assert "if (feedbackWired) return" in source
    assert "if (!view || viewObserver) return" in source


def test_game_shell_exit_restores_overview_without_synthetic_sidebar_click():
    source = GAME_SHELL_JS.read_text(encoding="utf-8")
    assert "function leaveGameToOverview()" in source
    assert "exitGame();" in source
    assert "showView('overview')" in source
    assert "leaveToOverview: leaveGameToOverview" in source
    assert "addEventListener('click', leaveGameToOverview)" in source
    assert "overview.click()" not in source


def test_mobile_menu_boot_is_single_mount_and_event_driven():
    source = MOBILE_MENU_JS.read_text(encoding="utf-8")
    assert "window.__devpilotMobileAccordionMenuStable" in source
    assert "let mounted = false" in source
    assert "if (existingRoot)" in source
    assert "mounted = true" in source
    assert "if (syncFrame) return" in source
    assert "requestAnimationFrame(sync)" in source
    assert "MutationObserver" not in source


def test_first_game_entry_isolated_from_dashboard_feature_loader():
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")
    html = GAME_HTML.read_text(encoding="utf-8")
    assert "game: ['game-shell.js', 'build-game.js']" not in loader
    assert "gameAdvanced:" not in loader
    assert "'build-game-subphases.js'" not in loader
    assert "window.__devpilotLoadGameAdvanced" not in loader
    assert "/assets/build-game.js" in html
    assert "/assets/game/game-bootstrap.js" in html
    assert "/assets/feature-loader.js" not in html


def test_cockpit_mobile_safe_mode_skips_advanced_runtime():
    source = GAME_COCKPIT_JS.read_text(encoding="utf-8")
    assert "const MOBILE_QUERY = '(max-width: 900px)'" in source
    assert "if (isMobile()) return false" in source
    assert "if (isMobile()) {" in source
    assert "buildGameMobileSafe" in source
    assert "new MutationObserver" not in source


def test_cockpit_deduplicates_linux_task_fetches_and_caps_payload():
    source = GAME_COCKPIT_JS.read_text(encoding="utf-8")
    assert "let linuxRefreshInFlight = null" in source
    assert "if (linuxRefreshInFlight) return linuxRefreshInFlight" in source
    assert "limit=100" in source
    assert "limit=500" not in source


def test_cockpit_boot_is_idempotent_and_event_driven():
    source = GAME_COCKPIT_JS.read_text(encoding="utf-8")
    assert "if (window.__devpilotBuildGameCockpitReady) return" in source
    assert "window.__devpilotBuildGameCockpitReady = true" in source
    assert "devpilot:game:rendered" in source
    assert "devpilot:game:entered" in source
    assert "MutationObserver" not in source
