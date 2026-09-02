from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/acs-loader.js").read_text(encoding="utf-8")
GAME_INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_static_mount_precedes_spa_catch_all():
    static_mount = MAIN.index('app.mount("/assets", StaticFiles(directory=STATIC), name="assets")')
    spa_catch_all = MAIN.index('@app.get("/{path:path}", include_in_schema=False)')
    assert static_mount < spa_catch_all


def test_wrong_spa_document_rescues_game_index_before_authentication():
    assert "GAME_FALLBACK_PATHS" in LOADER
    assert "'/game/index.html'" in LOADER
    assert "/assets/game/index.html" in LOADER
    assert LOADER.index("GAME_FALLBACK_PATHS") < LOADER.index("TOKEN_KEY")
    assert LOADER.index("window.location.replace(target)") < LOADER.index("TOKEN_KEY")


def test_direct_static_game_document_is_not_dashboard_shell():
    assert 'data-devpilot-game-standalone="1"' in GAME_INDEX
    assert '/assets/game/runtime.js' in GAME_INDEX
    assert '/assets/build-game.js' in GAME_INDEX
    assert '/assets/game/game-bootstrap.js' in GAME_INDEX
    assert '/assets/app.js' not in GAME_INDEX
    assert '/assets/feature-loader.js' not in GAME_INDEX
    assert '/assets/acs-loader.js' not in GAME_INDEX
