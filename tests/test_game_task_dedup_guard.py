from pathlib import Path


GUARD = Path("app/static/game/task-payload-guard.js")


def test_game_guard_installs_only_once_and_exposes_dedup_capability():
    text = GUARD.read_text(encoding="utf-8")

    assert "__devpilotGameTaskPayloadGuardInstalled" in text
    assert "if (window[INSTALL_FLAG]) return;" in text
    assert "window.__devpilotGameCreateDedup = true;" in text


def test_game_guard_reuses_same_mission_phase_instead_of_posting_twice():
    text = GUARD.read_text(encoding="utf-8")

    assert "gameCreationIdentity" in text
    assert "const gameCreationLocks = new Map();" in text
    assert "game-create:dedupe:join" in text
    assert "game-create:dedupe:existing" in text
    assert "const existing = await findGameCreation(options);" in text
    assert "Esta etapa já está registrada. A tarefa existente será reutilizada." in text


def test_game_guard_keeps_existing_post_failure_recovery():
    text = GUARD.read_text(encoding="utf-8")

    assert "recoverGameCreation(options)" in text
    assert "findGameCreation(options, 350)" in text
    assert "game-create:recover:end" in text
