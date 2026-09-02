from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")

REVISION = "game-unified-v73-20260902"


def test_first_render_has_only_three_critical_scripts():
    assert INDEX.count('<script src="/assets/') == 3
    assert '/assets/game/runtime.js' in INDEX
    assert '/assets/build-game.js' in INDEX
    assert '/assets/game/game-bootstrap.js' in INDEX
    assert '/assets/game/action-runtime.js' not in INDEX


def test_core_render_finishes_before_enhancements_start():
    core = BOOT.index("await withTimeout(window.loadBuildGame()")
    ready = BOOT.index("window.__devpilotGameCoreReady = true")
    enhancements = BOOT.index("startEnhancements();")
    assert core < ready < enhancements
    assert "requestAnimationFrame" in BOOT


def test_entry_enhancements_do_not_wrap_the_loader():
    assert "'game/action-runtime.js'" not in BOOT
    assert "'game/task-payload-guard.js'" in BOOT
    assert "'game/objective-controls.js'" in BOOT
    assert "'game/delivery-gate.js'" in BOOT
    assert "const REQUIRED_ASSET" not in BOOT
    assert "REQUIRED_TIMEOUT_MS" not in BOOT


def test_legacy_action_runtime_has_no_recursive_loader_loop():
    assert "while (loadRequested)" not in ACTION
    assert "loadRequested = true" not in ACTION


def test_cache_revision_is_current():
    assert REVISION in INDEX
    assert REVISION in BOOT
