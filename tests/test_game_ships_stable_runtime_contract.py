from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
GAME_BOOTSTRAP = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
GAME_RUNTIME = (ROOT / "app/static/game/runtime.js").read_text(encoding="utf-8")
BUILD_GAME = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")
PROJECTS = (ROOT / "app/static/mobile-project-card-compact.js").read_text(encoding="utf-8")


def test_standalone_game_assets_are_cache_busted_and_never_start_blank():
    revision = "game-development-v80-20260902"
    assert revision in GAME_INDEX
    assert 'data-game-boot-state="loading"' in GAME_INDEX
    assert 'data-game-critical-boot-v80' in GAME_INDEX
    assert "/assets/game/runtime.js" in GAME_INDEX
    assert "/assets/build-game.js" in GAME_INDEX
    assert "/assets/game/game-bootstrap.js" in GAME_INDEX


def test_standalone_boot_requires_real_render_or_shows_recovery():
    assert "CORE_TIMEOUT_MS = 12000" in GAME_BOOTSTRAP
    assert "showBooting" in GAME_BOOTSTRAP
    assert "showBootError" in GAME_BOOTSTRAP
    assert "hasShell" in GAME_BOOTSTRAP
    assert "Tentar novamente" in GAME_BOOTSTRAP
    assert "Voltar ao painel" in GAME_BOOTSTRAP
    assert "startEnhancements" in GAME_BOOTSTRAP
    assert "game/development-continuity.js" in GAME_BOOTSTRAP


def test_game_runtime_is_explicitly_exported_for_mobile_browsers():
    assert "window.api = api;" in GAME_RUNTIME
    assert "window.toast = toast;" in GAME_RUNTIME
    assert "window.showView = showView;" in GAME_RUNTIME
    assert "window.__devpilotGameApiReady = true;" in GAME_RUNTIME
    assert "window.__devpilotGameCompactRuntime = true;" in GAME_RUNTIME


def test_standalone_game_rewrites_heavy_payloads_to_compact_routes():
    assert "function standaloneRoute(path, options = {})" in GAME_RUNTIME
    assert "/ui/projects?limit=100" in GAME_RUNTIME
    assert "/ui/game-tasks?project_id=" in GAME_RUNTIME
    assert "limit=80" in GAME_RUNTIME
    assert "GAME_PIPELINE_MARKER" in GAME_RUNTIME
    assert "normalizeGameTasks" in GAME_RUNTIME


def test_real_build_game_engine_is_present():
    assert "[DEVPILOT_BUILD_GAME_PIPELINE_V2]" in BUILD_GAME
    assert "window.loadBuildGame = async () =>" in BUILD_GAME
    assert "const phases = [" in BUILD_GAME
    assert "Planejamento" in BUILD_GAME
    assert "Implementação" in BUILD_GAME
    assert "Entrega e revisão" in BUILD_GAME


def test_projects_keep_ships_and_direct_game_entry_in_light_runtime():
    assert "project-lite-ship-hangar" in PROJECTS
    assert "project-lite-ship-svg" in PROJECTS
    assert "data-project-game" in PROJECTS
    assert "devpilot-build-game-project" in PROJECTS
    assert "window.location.assign(GAME_URL)" in PROJECTS
