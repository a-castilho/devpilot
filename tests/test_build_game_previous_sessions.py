from pathlib import Path


SOURCE = Path("app/static/build-game-new-session.js")


def test_new_game_is_blocked_until_current_game_is_complete():
    source = SOURCE.read_text(encoding="utf-8")

    assert "canStartNewGame" in source
    assert "Conclua a partida atual antes de iniciar uma nova." in source
    assert "event.stopImmediatePropagation()" in source
    assert "currentProgress().completed" in source


def test_completed_games_are_archived_per_project():
    source = SOURCE.read_text(encoding="utf-8")

    assert "devpilot-build-game-history" in source
    assert "archiveCompletedMission" in source
    assert "completed_at" in source
    assert "historyKey(project)" in source


def test_user_can_open_a_previous_completed_game():
    source = SOURCE.read_text(encoding="utf-8")

    assert "Partidas anteriores" in source
    assert "data-previous-game-select" in source
    assert "data-open-previous-game" in source
    assert "openMission(projectId(), mission)" in source
    assert "sessionStorage.setItem(REOPEN_KEY, project)" in source
