from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_first_render_has_only_three_critical_scripts():
    assert INDEX.count('<script src="/assets/') == 3
    assert '/assets/game/runtime.js' in INDEX
    assert '/assets/build-game.js' in INDEX
    assert '/assets/game/game-bootstrap.js' in INDEX
    assert '/assets/game/action-runtime.js' not in INDEX


def test_core_render_finishes_before_any_enhancement_starts():
    core = BOOT.index("await withTimeout(window.loadBuildGame()")
    ready = BOOT.index("window.__devpilotGameCoreReady = true")
    enhancements = BOOT.index("startEnhancementsAfterPaint();")
    assert core < ready < enhancements
    assert "requestAnimationFrame" in BOOT
    assert "await yieldToBrowser();" in BOOT


def test_action_runtime_is_first_post_paint_enhancement():
    assert BOOT.index("'game/action-runtime.js'") < BOOT.index("'game/task-payload-guard.js'")
    assert "const REQUIRED_ASSET" not in BOOT
    assert "REQUIRED_TIMEOUT_MS" not in BOOT


def test_action_runtime_never_replays_loader_in_a_while_loop():
    assert "while (loadRequested)" not in ACTION
    assert "loadRequested = true" not in ACTION
    assert "coalescedLoadCount += 1" in ACTION
    assert "return loadInFlight" in ACTION
    assert "Promise.resolve().then(async () =>" in ACTION


def test_cache_revision_forces_browsers_off_regressed_assets():
    revision = "release-1.2.0-game-entry-stable-v64-20260902"
    assert revision in INDEX
    assert revision in BOOT
