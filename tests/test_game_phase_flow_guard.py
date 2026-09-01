from pathlib import Path

INDEX = Path("app/static/game/index.html").read_text(encoding="utf-8")
SOURCE = Path("app/static/game/phase-flow-guard.js").read_text(encoding="utf-8")


def test_standalone_loads_phase_guard_after_inline_approval():
    assert "game-v55-flow-guard-20260901" in INDEX
    assert "/assets/game/phase-flow-guard.js" in INDEX
    assert INDEX.index("/assets/game/inline-approval.js") < INDEX.index("/assets/game/phase-flow-guard.js")
    assert INDEX.index("/assets/game/phase-flow-guard.js") < INDEX.index("/assets/game/neon-layout.js")


def test_planning_is_a_blocking_status_and_flow_auto_refreshes():
    assert "'planning'" in SOURCE
    assert "BLOCKING_STATUSES" in SOURCE
    assert "AUTO_REFRESH_STATUSES" in SOURCE
    assert "POLL_MS = 2500" in SOURCE
    assert "Fase em andamento" in SOURCE


def test_phase_launch_is_idempotent_in_the_browser_runtime():
    assert "launchLocks.has(key)" in SOURCE
    assert "event.stopImmediatePropagation()" in SOURCE
    assert "button.dataset.gameFlowLaunching = '1'" in SOURCE
    assert "verifyLaunch(key, phaseId)" in SOURCE


def test_approval_remains_inside_the_game():
    assert "awaiting_approval" in SOURCE
    assert "data-game-inline-approve" in SOURCE
    assert "✓ Aprovar fase" in SOURCE
    assert "/approve`" in SOURCE


def test_guard_keeps_task_queries_bounded_for_low_memory_runtime():
    assert "limit=120" in SOURCE
