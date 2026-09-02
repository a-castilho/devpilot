from pathlib import Path


GUARD = Path("app/static/game/task-payload-guard.js")


def test_game_guard_installs_once_and_exposes_dedup_capability():
    text = GUARD.read_text(encoding="utf-8")

    assert "__devpilotGameTaskGuardV73" in text
    assert "if (window.__devpilotGameTaskGuardV73) return" in text
    assert "window.__devpilotGameCreateDedup = true" in text
    assert "window.__devpilotGameCreateRecovery = true" in text


def test_game_guard_dedupes_only_same_project_mission_phase_and_title():
    text = GUARD.read_text(encoding="utf-8")

    assert "const identityFrom = options =>" in text
    assert "const projectId" in text
    assert "promptValue(prompt, 'PARTIDA')" in text
    assert "promptValue(prompt, 'FASE')" in text
    assert "const title = String(payload.title || '').trim();" in text
    assert "key:`${projectId}::${mission}::${phase}::${title}`" in text
    assert "const locks = new Map();" in text
    assert "const current = locks.get(identity.key);" in text
    assert "if (current)" in text
    assert "return current;" in text


def test_failed_phase_is_not_reused_by_recovery():
    text = GUARD.read_text(encoding="utf-8")

    assert "const FAILED = new Set" in text
    assert "'failed'" in text
    assert "'cancelled'" in text
    assert "'canceled'" in text
    assert "'archived'" in text
    assert "!FAILED.has(normalize(task.status))" in text


def test_recovery_only_runs_after_uncertain_post_failure():
    text = GUARD.read_text(encoding="utf-8")

    post = text.index("const result = await originalApi(path, options);")
    recover = text.index("const recovered = await recover(identity);")
    assert post < recover
    assert "/ui/game-tasks?project_id=" in text
    assert "timeoutMs:3500" in text
    assert "retry:false" in text
