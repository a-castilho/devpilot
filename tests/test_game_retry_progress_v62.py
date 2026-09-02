from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BUILD = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")
ROUTES = (ROOT / "app/frontend_ui_routes.py").read_text(encoding="utf-8")


def test_retry_after_failed_phase_still_creates_a_new_real_task():
    assert "NON_RECOVERABLE_STATUSES" in GUARD
    assert "'failed'" in GUARD
    assert "const result = await originalApi(path, options);" in GUARD
    assert "window.__devpilotGameRetryCreatesNewTask = true;" in GUARD
    assert "game-create:direct:start" in GUARD


def test_dedupe_still_distinguishes_phase_gate_and_correction_by_title():
    assert "const creationKind = (prompt, title)" in GUARD
    assert "normalizeTitle(title)" in GUARD
    assert "creationKind(prompt, payload?.title)" in GUARD
    assert "creationKind(taskPrompt, task?.title)" in GUARD
    assert '"title": row.title' in ROUTES


def test_recovery_rejects_old_failed_task_without_a_preflight_request():
    assert "canRecoverCreation" in GUARD
    assert "matchesIdentity(task, identity) && canRecoverCreation(task)" in GUARD
    assert "const previous = await findGameCreations(options);" not in GUARD
    assert "game-create:dedupe:check" not in GUARD
    assert "window.__devpilotGameNoPreflightV63 = true;" in GUARD


def test_build_game_still_reloads_history_immediately_after_new_attempt():
    assert "const task = await api('/tasks'" in BUILD
    assert "await window.loadBuildGame();" in BUILD
    assert "order_by(Task.created_at.desc())" in ROUTES


def test_mobile_cache_keeps_v60_and_v62_contracts_while_forcing_v63_assets():
    revision = "release-1.2.0-game-core-first-v60-20260902-retry-v62-mobile-fast-v63"
    assert revision in BOOT
    assert INDEX.count(revision) >= 5
    assert "'game/task-payload-guard.js'" in BOOT
    assert "mobileRuntime ? 90 : 45" in BOOT
