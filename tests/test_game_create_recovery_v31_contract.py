from pathlib import Path


GUARD = Path("app/static/game/task-payload-guard.js")
GAME_HTML = Path("app/static/game/index.html")
BOOT = Path("app/static/game/game-bootstrap.js")


def test_game_recovers_uncertain_post_without_retrying_creation():
    source = GUARD.read_text(encoding="utf-8")
    assert "const recover = async identity" in source
    assert "PARTIDA" in source
    assert "FASE" in source
    assert "/ui/game-tasks?project_id=" in source
    assert "const result = await originalApi(path, options);" in source
    assert "const recovered = await recover(identity);" in source
    assert source.index("const result = await originalApi(path, options);") < source.index("const recovered = await recover(identity);")
    assert "window.__devpilotGameCreateRecovery = true" in source


def test_game_cache_revision_is_v73_and_guard_is_lazy():
    html = GAME_HTML.read_text(encoding="utf-8")
    boot = BOOT.read_text(encoding="utf-8")
    revision = "game-unified-v73-20260902"
    assert revision in html
    assert revision in boot
    assert "/assets/game/task-payload-guard.js" not in html
    assert "'game/task-payload-guard.js'" in boot
