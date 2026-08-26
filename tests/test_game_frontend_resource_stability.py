from pathlib import Path


GAME_SHELL_JS = Path("app/static/game-shell.js")
GAME_COCKPIT_JS = Path("app/static/build-game-cockpit.js")
MOBILE_MENU_JS = Path("app/static/mobile-accordion-menu.js")
FEATURE_LOADER_JS = Path("app/static/feature-loader.js")


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


def test_mobile_menu_boot_is_single_mount_and_wait_observer_is_released():
    source = MOBILE_MENU_JS.read_text(encoding="utf-8")

    assert "if (document.querySelector('.mobile-simple-nav')) return true" in source
    assert "if (waitObserver) return" in source
    assert "waitObserver?.disconnect()" in source
    assert "waitObserver = null" in source


def test_first_game_entry_loads_only_lightweight_core():
    source = FEATURE_LOADER_JS.read_text(encoding="utf-8")

    assert "game: ['game-shell.js', 'build-game.js']" in source
    assert "gameAdvanced:" in source
    assert "'build-game-subphases.js'" in source
    assert "window.__devpilotLoadGameAdvanced" in source
    assert "devpilot:feature-ready" in source
    assert "await loadScript(file)" in source


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
