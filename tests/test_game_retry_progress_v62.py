from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BUILD = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")
ROUTES = (ROOT / "app/frontend_ui_routes.py").read_text(encoding="utf-8")


def test_retry_after_failed_phase_creates_a_new_real_task():
    assert "RETRYABLE_STATUSES" in GUARD
    assert "'failed'" in GUARD
    assert "if (canReusePersistedCreation(latest))" in GUARD
    assert "game-create:retry:new-attempt" in GUARD
    assert "const result = await originalApi(path, options);" in GUARD
    assert "window.__devpilotGameRetryCreatesNewTask = true;" in GUARD


def test_persistent_dedupe_distinguishes_phase_gate_and_correction_by_title():
    assert "const creationKind = (prompt, title)" in GUARD
    assert "normalizeTitle(title)" in GUARD
    assert "creationKind(prompt, payload?.title)" in GUARD
    assert "creationKind(taskPrompt, task?.title)" in GUARD
    assert '"title": row.title' in ROUTES


def test_retry_recovery_never_reuses_a_failed_task_that_existed_before_post():
    assert "const previous = await findGameCreations(options);" in GUARD
    assert "previousIds = new Set(" in GUARD
    assert "recoverGameCreation(options, previousIds)" in GUARD
    assert "!excludedIds.has(String(task?.id || ''))" in GUARD


def test_build_game_still_reloads_history_immediately_after_new_attempt():
    assert "const task = await api('/tasks'" in BUILD
    assert "await window.loadBuildGame();" in BUILD
    assert "order_by(Task.created_at.desc())" in ROUTES


def test_mobile_receives_retry_v62_guard_instead_of_cached_broken_guard():
    revision = "release-1.2.0-game-core-first-v60-20260902-retry-v62"
    assert revision in BOOT
    assert revision in INDEX
    assert "'game/task-payload-guard.js'" in BOOT
