from pathlib import Path


GUARD = Path("app/static/game/task-payload-guard.js")


def test_game_guard_installs_once_and_keeps_inflight_dedup():
    text = GUARD.read_text(encoding="utf-8")

    assert "__devpilotGameTaskPayloadGuardInstalled" in text
    assert "if (window[INSTALL_FLAG]) return;" in text
    assert "const gameCreationLocks = new Map();" in text
    assert "game-create:dedupe:join" in text
    assert "window.__devpilotGameCreateDedup = true;" in text


def test_game_guard_keeps_semantic_identity_for_phase_gate_and_correction():
    text = GUARD.read_text(encoding="utf-8")

    assert "gameCreationIdentity" in text
    assert "creationKind" in text
    assert "normalizeTitle" in text
    assert "creationKind(prompt, payload?.title)" in text
    assert "creationKind(taskPrompt, task?.title)" in text


def test_mobile_creation_posts_immediately_without_history_preflight():
    text = GUARD.read_text(encoding="utf-8")

    assert "game-create:direct:start" in text
    assert "const result = await originalApi(path, options);" in text
    assert "game-create:dedupe:check" not in text
    assert "const previous = await findGameCreations(options);" not in text
    assert "previousIds = new Set(" not in text
    assert "window.__devpilotGameNoPreflightV63 = true;" in text


def test_failed_old_task_is_never_accepted_as_post_failure_recovery():
    text = GUARD.read_text(encoding="utf-8")

    assert "NON_RECOVERABLE_STATUSES" in text
    assert "'failed'" in text
    assert "canRecoverCreation" in text
    assert "matchesIdentity(task, identity) && canRecoverCreation(task)" in text
    assert "game-create:recover:end" in text
    assert "window.__devpilotGameRetryCreatesNewTask = true;" in text
