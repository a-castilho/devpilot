from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_game_document_is_isolated_from_dashboard_feature_loader():
    html = (STATIC / "game" / "index.html").read_text(encoding="utf-8")

    assert 'data-devpilot-game-standalone="1"' in html
    assert '/assets/game/game-bootstrap.js' in html
    assert '/assets/build-game.js' in html
    assert '/assets/game/game-pilot-panel.js' in html
    assert '/assets/game/game-pilot-panel.css' in html
    assert '/assets/feature-loader.js' not in html
    assert 'class="sidebar"' not in html


def test_dashboard_game_placeholder_navigates_instead_of_lazy_loading_game_bundle():
    loader = (STATIC / "feature-loader.js").read_text(encoding="utf-8")

    assert "window.location.assign('/game/index.html')" in loader
    assert "game: ['game-shell.js', 'build-game.js']" not in loader
    assert "addPlaceholder('game', 'Modo Jogo')" in loader


def test_standalone_game_has_global_logout_exit_and_auth_guard():
    bootstrap = (STATIC / "game" / "game-bootstrap.js").read_text(encoding="utf-8")

    assert "localStorage.removeItem(TOKEN_KEY)" in bootstrap
    assert "sessionStorage.clear()" in bootstrap
    assert "window.location.replace('/')" in bootstrap
    assert "window.location.assign('/')" not in bootstrap
    assert "localStorage.getItem(TOKEN_KEY)" in bootstrap
    assert "fetch('/api/auth/me'" in bootstrap
    assert "window.loadBuildGame" in bootstrap
    assert "devpilot:game:standalone-ready" in bootstrap


def test_pilot_panel_reuses_real_tasks_and_safe_run_contracts():
    panel = (STATIC / "game" / "game-pilot-panel.js").read_text(encoding="utf-8")

    assert "/tasks?project_id=${encodeURIComponent(id)}&limit=100" in panel
    assert "/task-runs/latest?limit=500" in panel
    assert "/task-runs/${encodeURIComponent(runId)}" in panel
    assert "/tasks/${encodeURIComponent(taskId)}/retry" in panel
    assert "Escudo de testes" in panel
    assert "Scanner de segurança" in panel
    assert "Canhão de reparo" in panel
    assert "REFRESH_MS = 15000" in panel
    assert "MutationObserver" not in panel


def test_visual_game_entry_uses_same_isolated_url():
    entry = (STATIC / "game-entry.js").read_text(encoding="utf-8")

    assert "const GAME_URL = '/game/index.html'" in entry
    assert "window.location.assign(GAME_URL)" in entry
    assert "__devpilotLoadFeature?.('game')" not in entry
