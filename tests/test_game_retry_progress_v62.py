from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BUILD = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")
ROUTES = (ROOT / "app/frontend_ui_routes.py").read_text(encoding="utf-8")


def test_retry_after_failed_phase_creates_new_real_task():
    assert "const FAILED = new Set" in GUARD
    assert "failed" in GUARD
    assert "const result = await originalApi(path, options);" in GUARD
    assert "window.__devpilotGameCreateDedup = true" in GUARD
    assert "window.__devpilotGameCreateRecovery = true" in GUARD
    assert "createPhaseTask(stateNow.currentPhaseId, stateNow.goal, {force:true})" in BUILD


def test_dedupe_distinguishes_phase_and_gate_by_title():
    assert "const title = String(payload.title || '').trim();" in GUARD
    assert "title, key:`${projectId}::${mission}::${phase}::${title}`" in GUARD
    assert "String(task?.title || '').trim() === identity.title" in GUARD
    assert '"title": row.title' in ROUTES


def test_recovery_rejects_failed_task_and_has_no_preflight():
    assert "!FAILED.has(normalize(task.status))" in GUARD
    assert "findGameCreations" not in GUARD
    post = GUARD.index("const result = await originalApi(path, options);")
    recover = GUARD.index("const recovered = await recover(identity);")
    assert post < recover


def test_build_game_reloads_history_after_new_attempt():
    assert "return await api('/tasks'," in BUILD
    assert "await window.loadBuildGame();" in BUILD
    assert "order_by(Task.created_at.desc())" in ROUTES


def test_cache_and_guard_are_v73():
    revision = "game-unified-v73-20260902"
    assert revision in BOOT
    assert INDEX.count(revision) >= 5
    assert "'game/task-payload-guard.js'" in BOOT
    assert "'game/action-runtime.js'" not in BOOT
