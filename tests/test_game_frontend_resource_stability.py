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


def test_game_bundle_is_lazy_and_feature_ready_drives_handoff():
    source = FEATURE_LOADER_JS.read_text(encoding="utf-8")

    assert "game: [" in source
    assert "'game-shell.js'" in source
    assert "devpilot:feature-ready" in source
    assert "await loadScript(file)" in source


def test_cockpit_does_not_refresh_linux_economy_when_already_mounted():
    source = GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "if (shell.querySelector('[data-build-game-cockpit]')) return false" in source
    assert "new MutationObserver(queueSyncOnlyWhenCockpitMissing)" in source
    assert "if (view.querySelector('[data-build-game-cockpit]')) return" in source


def test_cockpit_deduplicates_linux_task_fetches_and_caps_payload():
    source = GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "const TASK_FETCH_LIMIT = 100" in source
    assert "let linuxRefreshInFlight = null" in source
    assert "if (linuxRefreshInFlight && !force) return linuxRefreshInFlight" in source
    assert "limit=${TASK_FETCH_LIMIT}" in source
    assert "limit=500" not in source


def test_cockpit_boot_is_idempotent():
    source = GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "if (window.__devpilotBuildGameCockpitReady) return" in source
    assert "window.__devpilotBuildGameCockpitReady = true" in source
    assert "buildGameCockpitObserved" in source
