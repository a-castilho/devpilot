from pathlib import Path


GUARD = Path("app/static/game/task-payload-guard.js")
GAME_HTML = Path("app/static/game/index.html")


def test_game_recovers_uncertain_post_without_retrying_creation():
    source = GUARD.read_text(encoding="utf-8")
    assert "recoverGameCreation(options)" in source
    assert "PARTIDA" in source
    assert "FASE" in source
    assert "/ui/game-tasks?project_id=" in source
    assert "game-create:recover:end" in source
    assert "window.__devpilotGameCreateRecovery = true" in source


def test_game_cache_revision_is_bumped():
    html = GAME_HTML.read_text(encoding="utf-8")
    assert "frontend-v31" in html
    assert "task-payload-guard.js?v=frontend-v31" in html
