from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")

REVISION = "game-unified-v73-20260902"


def test_legacy_action_runtime_remains_non_recursive_when_loaded_elsewhere():
    assert "while (loadRequested)" not in ACTION
    assert "loadRequested = true" not in ACTION
    assert "do {" not in ACTION


def test_standalone_boot_no_longer_depends_on_action_runtime_wrapper():
    assert "'game/action-runtime.js'" not in BOOT
    assert "'game/task-payload-guard.js'" in BOOT
    assert "'game/objective-controls.js'" in BOOT
    assert "'game/delivery-gate.js'" in BOOT
    assert "await withTimeout(window.loadBuildGame()" in BOOT
    assert "window.__devpilotGameCoreReady = true" in BOOT
    assert "startEnhancements();" in BOOT
    assert BOOT.index("await withTimeout(window.loadBuildGame()") < BOOT.index("window.__devpilotGameCoreReady = true") < BOOT.index("startEnhancements();")


def test_standalone_assets_share_v73_revision():
    assert REVISION in INDEX
    assert REVISION in BOOT
    assert INDEX.count(REVISION) >= 5
    assert 'data-devpilot-game-version="v73"' in INDEX
