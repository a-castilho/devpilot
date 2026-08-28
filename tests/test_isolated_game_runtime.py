from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_game_document_is_isolated_from_dashboard_feature_loader():
    html = (STATIC / "game" / "index.html").read_text(encoding="utf-8")

    assert 'data-devpilot-game-standalone="1"' in html
    assert '/assets/game/game-bootstrap.js' in html
    assert '/assets/build-game.js' in html
    assert '/assets/feature-loader.js' not in html
    assert 'class="sidebar"' not in html


def test_standalone_game_bounds_initial_task_payload_before_bootstrap():
    html = (STATIC / "game" / "index.html").read_text(encoding="utf-8")
    guard = (STATIC / "game" / "task-payload-guard.js").read_text(encoding="utf-8")

    build_index = html.index('/assets/build-game.js')
    guard_index = html.index('/assets/game/task-payload-guard.js')
    bootstrap_index = html.index('/assets/game/game-bootstrap.js')

    assert build_index < guard_index < bootstrap_index
    assert "const GAME_TASK_LIMIT = 100" in guard
    assert "requestPath.startsWith('/tasks?')" in guard
    assert "requestPath.includes('limit=500')" in guard
    assert "replace(/([?&]limit=)500\\b/" in guard


def test_dashboard_game_placeholder_navigates_instead_of_lazy_loading_game_bundle():
    loader = (STATIC / "feature-loader.js").read_text(encoding="utf-8")

    assert "window.location.assign('/game/index.html')" in loader
    assert "game: ['game-shell.js', 'build-game.js']" not in loader
    assert "addPlaceholder('game', 'Modo Jogo')" in loader


def test_standalone_game_has_full_navigation_exit_and_auth_guard():
    bootstrap = (STATIC / "game" / "game-bootstrap.js").read_text(encoding="utf-8")

    assert "window.location.assign('/')" in bootstrap
    assert "localStorage.getItem('devpilot-token')" in bootstrap
    assert "fetch('/api/auth/me'" in bootstrap
    assert "window.loadBuildGame" in bootstrap
    assert "devpilot:game:standalone-ready" in bootstrap


def test_visual_game_entry_uses_same_isolated_url():
    entry = (STATIC / "game-entry.js").read_text(encoding="utf-8")

    assert "const GAME_URL = '/game/index.html'" in entry
    assert "window.location.assign(GAME_URL)" in entry
    assert "__devpilotLoadFeature?.('game')" not in entry
