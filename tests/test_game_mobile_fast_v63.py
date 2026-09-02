from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")


def test_mobile_phase_action_has_no_history_get_before_post():
    post = GUARD.index("const result = await originalApi(path, options);")
    recover = GUARD.index("const recovered = await recover(identity);")
    assert post < recover
    assert "findGameCreations" not in GUARD


def test_duplicate_taps_are_coalesced_in_memory():
    assert "const locks = new Map();" in GUARD
    assert "const current = locks.get(identity.key);" in GUARD
    assert "if (current)" in GUARD
    assert "return current;" in GUARD


def test_failed_history_is_not_accepted_as_successful_recovery():
    assert "const FAILED = new Set" in GUARD
    assert "failed" in GUARD
    assert "!FAILED.has(normalize(task.status))" in GUARD


def test_android_gets_one_current_revision_for_critical_assets():
    revision = "game-unified-v73-20260902"
    assert revision in BOOT
    assert INDEX.count(revision) >= 5
    assert "/assets/game/runtime.js" in INDEX
    assert "/assets/build-game.js" in INDEX
    assert "/assets/game/game-bootstrap.js" in INDEX


def test_entry_modules_yield_between_each_load_without_mobile_poll_loop():
    assert "await new Promise(resolve => window.setTimeout(resolve, 0));" in BOOT
    assert "mobileRuntime" not in BOOT


def test_observer_regression_is_removed_from_current_standalone_controls():
    assert "MutationObserver" not in OBJECTIVE
    assert "devpilot:game:state" in OBJECTIVE
    assert "'game/start-round-mobile.js'" not in BOOT
