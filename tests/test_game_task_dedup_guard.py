from pathlib import Path


GUARD = Path("app/static/game/task-payload-guard.js")


def test_game_guard_installs_only_once_and_exposes_dedup_capability():
    text = GUARD.read_text(encoding="utf-8")

    assert "__devpilotGameTaskPayloadGuardInstalled" in text
    assert "if (window[INSTALL_FLAG]) return;" in text
    assert "window.__devpilotGameCreateDedup = true;" in text
    assert "window.__devpilotGameRetryCreatesNewTask = true;" in text
    assert "window.__devpilotGameCreationIdentityV62 = true;" in text


def test_game_guard_dedupes_only_same_semantic_game_action():
    text = GUARD.read_text(encoding="utf-8")

    assert "gameCreationIdentity" in text
    assert "creationKind" in text
    assert "normalizeTitle" in text
    assert "creationKind(prompt, payload?.title)" in text
    assert "creationKind(taskPrompt, task?.title)" in text
    assert "const gameCreationLocks = new Map();" in text
    assert "game-create:dedupe:join" in text
    assert "game-create:dedupe:existing" in text
    assert "Esta etapa já está registrada. A tarefa existente será reutilizada." in text


def test_failed_phase_is_not_reused_when_user_taps_retry():
    text = GUARD.read_text(encoding="utf-8")

    assert "RETRYABLE_STATUSES" in text
    assert "'failed'" in text
    assert "canReusePersistedCreation" in text
    assert "if (canReusePersistedCreation(latest))" in text
    assert "game-create:retry:new-attempt" in text
    assert "const result = await originalApi(path, options);" in text


def test_retry_recovery_cannot_return_the_old_failed_task():
    text = GUARD.read_text(encoding="utf-8")

    assert "const previous = await findGameCreations(options);" in text
    assert "previousIds = new Set(" in text
    assert "recoverGameCreation(options, previousIds)" in text
    assert "!excludedIds.has(String(task?.id || ''))" in text
    assert "game-create:recover:end" in text
