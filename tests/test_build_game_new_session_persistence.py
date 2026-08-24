from pathlib import Path


SOURCE = Path("app/static/build-game-new-session.js")


def test_new_game_is_persisted_per_project():
    source = SOURCE.read_text(encoding="utf-8")

    assert "devpilot-build-game-saved-mission" in source
    assert "saveMissionForProject" in source
    assert "localStorage.setItem(savedMissionKey(project), mission)" in source
    assert "persisted: Boolean(project && nextMission)" in source


def test_saved_new_game_survives_reopening_project_card():
    source = SOURCE.read_text(encoding="utf-8")

    assert "[data-project-build-game]" in source
    assert "event.stopImmediatePropagation()" in source
    assert "sessionStorage.setItem(REOPEN_KEY, project)" in source
    assert "window.location.reload()" in source
    assert "reopenSavedGameAfterReload" in source
    assert "[data-view=\"build-game\"]" in source
