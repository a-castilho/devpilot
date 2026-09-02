from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
RUNTIME = (ROOT / "app/static/game/runtime.js").read_text(encoding="utf-8")


def test_game_document_loads_only_three_core_scripts_synchronously():
    assert INDEX.count('<script src=') == 3
    assert '/assets/game/runtime.js' in INDEX
    assert '/assets/build-game.js' in INDEX
    assert '/assets/game/game-bootstrap.js' in INDEX
    assert '/assets/game/objective-controls.js' not in INDEX
    assert '/assets/game/delivery-gate.js' not in INDEX


def test_optional_assets_load_only_after_core_render():
    assert 'OPTIONAL_ASSETS' in BOOT
    assert "window.__devpilotGameCoreReady = true" in BOOT
    assert "void loadEnhancements();" in BOOT
    assert "target?.querySelector('.build-game-shell')" in BOOT
    assert "devpilot:game:core-ready" in BOOT


def test_boot_starts_immediately_without_waiting_for_domcontentloaded():
    assert 'queueMicrotask' in BOOT
    assert "DOMContentLoaded" not in BOOT
    assert 'CORE_TIMEOUT_MS = 7000' in BOOT


def test_compact_startup_requests_are_bounded_and_not_retried():
    assert "timeoutMs: Number(options.timeoutMs || 5000), retry: false" in RUNTIME
    assert "options.retry !== false" in RUNTIME
    assert "window.__devpilotGameStartupRequestTimeoutMs = 5000" in RUNTIME
