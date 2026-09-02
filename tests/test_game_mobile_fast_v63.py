from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
START = (ROOT / "app/static/game/start-round-mobile.js").read_text(encoding="utf-8")
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")


def test_mobile_phase_action_has_no_history_get_before_post():
    post = GUARD.index("const result = await originalApi(path, options);")
    recover = GUARD.index("const recovered = await recoverGameCreation(options);")
    assert post < recover
    assert "const previous = await findGameCreations(options);" not in GUARD
    assert "game-create:dedupe:check" not in GUARD


def test_duplicate_taps_are_still_coalesced_in_memory():
    assert "const gameCreationLocks = new Map();" in GUARD
    assert "const inFlight = gameCreationLocks.get(identity.key);" in GUARD
    assert "if (inFlight)" in GUARD
    assert "return inFlight;" in GUARD


def test_failed_history_is_not_accepted_as_successful_recovery():
    assert "NON_RECOVERABLE_STATUSES" in GUARD
    assert "failed" in GUARD
    assert "canRecoverCreation(task)" in GUARD


def test_android_gets_one_consistent_current_revision_for_every_critical_asset():
    revision = "release-1.2.0-game-entry-minimal-v65-20260902"
    assert revision in BOOT
    assert INDEX.count(revision) == 5
    assert "/assets/game/runtime.js" in INDEX
    assert "/assets/build-game.js" in INDEX
    assert "/assets/game/game-bootstrap.js" in INDEX


def test_mobile_yields_longer_between_optional_modules():
    assert "const mobileRuntime" in BOOT
    assert "mobileRuntime ? 90 : 45" in BOOT
    assert "await yieldToBrowser();" in BOOT
    assert "requestIdleCallback" in BOOT


def test_observer_regression_is_removed_from_standalone_controls():
    assert "MutationObserver" not in START
    assert "MutationObserver" not in OBJECTIVE
    assert "devpilot:game:rendered" in START
    assert "devpilot:game:rendered" in OBJECTIVE
