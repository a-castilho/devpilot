from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_game_document_is_isolated_from_dashboard_feature_loader():
    html = (STATIC / "game" / "index.html").read_text(encoding="utf-8")

    assert 'data-devpilot-game-standalone="1"' in html
    assert 'data-devpilot-game-version="v73"' in html
    assert '/assets/game/game-bootstrap.js' in html
    assert '/assets/build-game.js' in html
    assert '/assets/feature-loader.js' not in html
    assert 'class="sidebar"' not in html


def test_standalone_game_keeps_only_three_critical_scripts_in_order():
    html = (STATIC / "game" / "index.html").read_text(encoding="utf-8")

    runtime = html.index('/assets/game/runtime.js')
    build = html.index('/assets/build-game.js')
    bootstrap = html.index('/assets/game/game-bootstrap.js')
    assert runtime < build < bootstrap
    assert html.count('<script src="/assets/') == 3
    assert '/assets/game/task-payload-guard.js' not in html
    assert '/assets/game/action-runtime.js' not in html


def test_standalone_runtime_uses_lightweight_projects_and_task_history():
    runtime = (STATIC / "game" / "runtime.js").read_text(encoding="utf-8")

    assert "function standaloneRoute(path, options = {})" in runtime
    assert "/ui/projects?limit=50" in runtime
    assert "include_project_id=" in runtime
    assert "/ui/game-tasks?project_id=" in runtime
    assert "limit=24" in runtime
    assert "GAME_PIPELINE_MARKER" in runtime
    assert "normalizeGameTasks" in runtime
    assert "window.__devpilotGameUsesLightweightProjects" not in runtime


def test_lightweight_projects_preserve_saved_game_project_outside_first_page():
    runtime = (STATIC / "game" / "runtime.js").read_text(encoding="utf-8")
    routes = (ROOT / "app" / "frontend_ui_routes.py").read_text(encoding="utf-8")

    assert "GAME_PROJECT_KEY" in runtime
    assert "localStorage.getItem(GAME_PROJECT_KEY)" in runtime
    assert "include_project_id=" in runtime
    assert "include_project_id: str | None = None" in routes
    assert "Project.id == include_project_id" in routes
    assert "Project.workspace_id == ws.id" in routes
    assert "rows.append(selected)" in routes


def test_game_task_guard_only_wraps_real_task_creation_and_bounds_trace():
    guard = (STATIC / "game" / "task-payload-guard.js").read_text(encoding="utf-8")

    assert "requestPath !== '/tasks' || method !== 'POST'" in guard
    assert "const locks = new Map();" in guard
    assert "const result = await originalApi(path, options);" in guard
    assert "const recovered = await recover(identity);" in guard
    assert guard.index("const result = await originalApi(path, options);") < guard.index("const recovered = await recover(identity);")
    assert "rows.length > 48" in guard
    assert "devpilot-game-debug" in guard


def test_game_boot_does_not_report_ready_after_real_load_failure():
    build = (STATIC / "build-game.js").read_text(encoding="utf-8")
    bootstrap = (STATIC / "game" / "game-bootstrap.js").read_text(encoding="utf-8")

    assert "window.__devpilotGameLoadError = failure" in build
    assert "throw failure" in build
    assert "window.__devpilotGameLoadError = null" in bootstrap
    assert "if (window.__devpilotGameLoadError) throw window.__devpilotGameLoadError" in bootstrap
    assert "showBootError" in bootstrap
    assert bootstrap.index("await withTimeout(window.loadBuildGame()") < bootstrap.index("window.__devpilotGameCoreReady = true")


def test_lightweight_game_history_strips_large_prompt_body():
    routes = (ROOT / "app" / "frontend_ui_routes.py").read_text(encoding="utf-8")

    assert '@router.get("/game-tasks")' in routes
    assert 'Task.title.like("[Jogo]%")' in routes
    assert "_game_prompt_metadata(row.prompt)" in routes
    assert '_GAME_METADATA_LABELS = ("PARTIDA", "FASE", "OBJETIVO")' in routes
    assert ".limit(limit)" in routes


def test_standalone_game_has_mobile_vertical_scroll_container():
    css = (STATIC / "game-shell.css").read_text(encoding="utf-8")

    assert 'body[data-devpilot-game-standalone="1"]' in css
    assert "height:100dvh" in css
    assert "grid-template-rows:auto minmax(0,1fr)" in css
    assert ".devpilot-game-stage" in css
    assert "overflow-y:auto" in css
    assert "touch-action:pan-y" in css
    assert "-webkit-overflow-scrolling:touch" in css


def test_dashboard_game_placeholder_navigates_instead_of_lazy_loading_game_bundle():
    loader = (STATIC / "feature-loader.js").read_text(encoding="utf-8")

    assert "window.location.assign('/game/index.html')" in loader
    assert "game: ['game-shell.js', 'build-game.js']" not in loader
    assert "addPlaceholder('game', 'Modo Jogo')" in loader


def test_standalone_game_has_exit_token_guard_and_real_controller_boot():
    bootstrap = (STATIC / "game" / "game-bootstrap.js").read_text(encoding="utf-8")
    build = (STATIC / "build-game.js").read_text(encoding="utf-8")

    assert "window.location.assign('/')" in bootstrap
    assert "localStorage.getItem('devpilot-token')" in bootstrap
    assert "window.loadBuildGame" in bootstrap
    assert "devpilot:game:enhancements-ready" in bootstrap
    assert "window.__devpilotGameControllerV73" in build


def test_visual_game_entry_uses_isolated_url_without_lazy_bundle():
    entry = (STATIC / "game-entry.js").read_text(encoding="utf-8")

    assert "const GAME_URL = '/game/index.html'" in entry
    assert "window.location.assign(GAME_URL)" in entry
    assert "__devpilotLoadFeature?.('game')" not in entry
