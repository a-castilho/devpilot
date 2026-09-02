from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_action_runtime_serializes_without_recursive_reload_loop():
    assert "if (loadInFlight)" in ACTION
    assert "coalescedLoadCount += 1" in ACTION
    assert "return loadInFlight" in ACTION
    assert "while (loadRequested)" not in ACTION
    assert "loadRequested = true" not in ACTION
    assert "do {" not in ACTION
    assert "now - previous < 650" in ACTION
    assert "event.stopImmediatePropagation()" in ACTION
    assert "__devpilotGameRunAction" in ACTION
    assert "devpilot:game:rendered" in ACTION


def test_boot_renders_core_before_action_runtime_enhancement():
    assert "'game/action-runtime.js'" in BOOT
    assert "const REQUIRED_ASSET" not in BOOT
    assert "REQUIRED_TIMEOUT_MS" not in BOOT
    assert "startEnhancementsAfterPaint" in BOOT
    assert "requestAnimationFrame" in BOOT
    assert BOOT.index("await withTimeout(window.loadBuildGame()") < BOOT.index("startEnhancementsAfterPaint();")
    assert BOOT.index("'game/action-runtime.js'") < BOOT.index("'game/task-payload-guard.js'")


def test_standalone_assets_have_current_entry_stability_revision():
    revision = "release-1.2.0-game-entry-minimal-v65-20260902"
    assert revision in INDEX
    assert revision in BOOT
    assert INDEX.count(revision) == 5
