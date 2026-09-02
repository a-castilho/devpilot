from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADER = (ROOT / "app/static/acs-loader.js").read_text(encoding="utf-8")
GAME_INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_spa_loader_redirects_all_legacy_game_routes_before_auth_boot():
    assert "GAME_FALLBACK_PATHS" in LOADER
    assert "new Set(['/game', '/game/', '/game/index.html'])" in LOADER
    assert "window.location.replace(target)" in LOADER
    assert "/assets/game/index.html" in LOADER
    assert LOADER.index("GAME_FALLBACK_PATHS") < LOADER.index("TOKEN_KEY")


def test_canonical_game_document_has_visible_boot_shell():
    assert 'data-devpilot-game-standalone="1"' in GAME_INDEX
    assert 'data-devpilot-game-version="v73"' in GAME_INDEX
    assert 'id="build-game-view"' in GAME_INDEX
    assert 'data-game-boot-state="loading"' in GAME_INDEX
    assert '/assets/game/game-bootstrap.js' in GAME_INDEX
