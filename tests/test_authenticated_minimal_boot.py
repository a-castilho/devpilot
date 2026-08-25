from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "app/static/acs-loader.js"
MAIN = ROOT / "app/main.py"


def test_authenticated_boot_has_strict_runtime_allowlist():
    source = LOADER.read_text(encoding="utf-8")
    assert "SAFE_AUTH_BOOT_SCRIPTS" in source
    assert "'app.js'" in source
    assert "'profile.js'" in source
    assert "'users.js'" in source
    assert "node.dataset.devpilotProgressive === '1'" in source
    assert "node.dataset.devpilotSuppressed = '1'" in source


def test_heavy_and_css_mutating_modules_are_not_allowed_during_boot():
    source = LOADER.read_text(encoding="utf-8")
    allowlist = source.split("SAFE_AUTH_BOOT_SCRIPTS = new Set([", 1)[1].split("]);", 1)[0]
    for name in (
        "tasks-lazy-load.js",
        "simplified-nav.js",
        "workspace-skins.js",
        "task-analytics.js",
        "build-game.js",
        "mobile-game-mode.js",
        "telemetry-capture.js",
    ):
        assert name not in allowlist


def test_scheduler_scripts_are_suppressed_without_deadlocking_loader():
    source = LOADER.read_text(encoding="utf-8")
    assert "queueMicrotask" in source
    assert "typeof node.onload === 'function'" in source
    assert "boot.suppressed" in source
    assert "window.__devpilotNativeBodyAppend" in source


def test_backend_may_keep_legacy_lists_but_browser_gate_is_authoritative():
    main = MAIN.read_text(encoding="utf-8")
    assert "_CORE_AUTHENTICATED_SCRIPTS" in main
    assert "_DEFERRED_AUTHENTICATED_SCRIPTS" in main
    source = LOADER.read_text(encoding="utf-8")
    assert "automaticRuntimeScript" in source
