from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "app" / "static" / "game-shell.js"
SUBPHASES = ROOT / "app" / "static" / "build-game-subphases.js"
REPAIR = ROOT / "app" / "static" / "build-game-repair-mission.js"


def test_game_shell_captures_base_loader_before_enhancement_wrappers():
    js = SHELL.read_text(encoding="utf-8")
    assert "window.__devpilotBaseLoadBuildGame = baseLoadBuildGame" in js
    assert "startLoaderGuard()" in js
    assert "window.setInterval" in js
    assert "}, 8);" in js


def test_initial_sidebar_entry_bypasses_heavy_enhancement_chain():
    js = SHELL.read_text(encoding="utf-8")
    assert "openBaseGameFromNavigation" in js
    assert "event.stopImmediatePropagation()" in js
    assert "await runBaseLoad()" in js
    assert "devpilot:game:base-ready" in js
    assert "DevPilotGameShell" in js
    assert "loadBase: runBaseLoad" in js


def test_base_loader_is_single_flight_and_deduplicates_concurrent_refreshes():
    js = SHELL.read_text(encoding="utf-8")
    assert "let loadInFlight = null" in js
    assert "if (loadInFlight)" in js
    assert "METRICS.dedupedLoads += 1" in js
    assert "loadInFlight = Promise.resolve()" in js
    assert "loadInFlight = null" in js


def test_view_observer_does_not_watch_game_subtree():
    js = SHELL.read_text(encoding="utf-8")
    marker = "viewObserver.observe(view, {attributes: true, attributeFilter: ['class']})"
    assert marker in js
    assert "viewObserver.observe(view, {childList" not in js
    assert "viewObserver.observe(view, {subtree" not in js


def test_heavy_enhancements_still_exist_but_are_not_required_for_base_entry():
    shell = SHELL.read_text(encoding="utf-8")
    subphases = SUBPHASES.read_text(encoding="utf-8")
    repair = REPAIR.read_text(encoding="utf-8")
    assert "build-game-subphases" in subphases
    assert "build-game-repair" in repair
    assert "await runBaseLoad()" in shell
    # Regression guard: base entry must not directly call their expensive endpoints.
    base_entry = shell[shell.index("async function openBaseGameFromNavigation"):shell.index("function wireGameFeedback")]
    assert "limit=500" not in base_entry
    assert "task-runs/latest" not in base_entry
