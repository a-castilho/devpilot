from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_game_document_is_isolated_from_dashboard_feature_loader():
    html = (STATIC / "game" / "index.html").read_text(encoding="utf-8")

    assert 'data-devpilot-game-standalone="1"' in html
    assert '/assets/game/game-bootstrap.js' in html
    assert '/assets/build-game.js' in html
    assert '/assets/feature-loader.js' not in html
    assert 'class="sidebar"' not in html


def test_standalone_game_uses_lightweight_task_history_before_bootstrap():
    html = (STATIC / "game" / "index.html").read_text(encoding="utf-8")
    guard = (STATIC / "game" / "task-payload-guard.js").read_text(encoding="utf-8")

    build_index = html.index('/assets/build-game.js')
    guard_index = html.index('/assets/game/task-payload-guard.js')
    bootstrap_index = html.index('/assets/game/game-bootstrap.js')

    assert build_index < guard_index < bootstrap_index
    assert "const GAME_TASK_LIMIT = 24" in guard
    assert "requestPath.startsWith('/tasks?')" in guard
    assert "new URLSearchParams" in guard
    assert "/ui/game-tasks?project_id=" in guard
    assert "__devpilotGameUsesLightweightHistory = true" in guard


def test_standalone_game_uses_lightweight_projects_and_boot_trace():
    guard = (STATIC / "game" / "task-payload-guard.js").read_text(encoding="utf-8")
    bootstrap = (STATIC / "game" / "game-bootstrap.js").read_text(encoding="utf-8")

    assert "const GAME_PROJECT_LIMIT = 50" in guard
    assert "requestPath === '/projects'" in guard
    assert "/ui/projects?limit=" in guard
    assert "__devpilotGameUsesLightweightProjects = true" in guard
    assert "__devpilotGameBootTrace" in guard
    assert "__devpilotGameTrace" in guard
    assert "trace('auth:start')" in bootstrap
    assert "trace('auth:end'" in bootstrap
    assert "trace('game-load:start')" in bootstrap
    assert "trace('game-load:end')" in bootstrap
    assert "trace('boot:ready')" in bootstrap


def test_lightweight_projects_preserve_saved_game_project_outside_first_page():
    guard = (STATIC / "game" / "task-payload-guard.js").read_text(encoding="utf-8")
    routes = (ROOT / "app" / "frontend_ui_routes.py").read_text(encoding="utf-8")

    assert "const GAME_PROJECT_KEY = 'devpilot-build-game-project'" in guard
    assert "localStorage.getItem(GAME_PROJECT_KEY)" in guard
    assert "include_project_id=" in guard
    assert "include_project_id: str | None = None" in routes
    assert "Project.id == include_project_id" in routes
    assert "Project.workspace_id == ws.id" in routes
    assert "rows.append(selected)" in routes


def test_game_boot_does_not_report_ready_after_lightweight_load_failure():
    guard = (STATIC / "game" / "task-payload-guard.js").read_text(encoding="utf-8")
    bootstrap = (STATIC / "game" / "game-bootstrap.js").read_text(encoding="utf-8")

    assert "window.__devpilotGameLoadError = error instanceof Error" in guard
    assert "stage === 'projects' || stage === 'game-tasks'" in guard
    assert "window.__devpilotGameLoadError = null" in bootstrap
    assert "if (window.__devpilotGameLoadError) throw window.__devpilotGameLoadError" in bootstrap
    assert bootstrap.index("if (window.__devpilotGameLoadError)") < bootstrap.index("trace('game-load:end')")
    assert bootstrap.index("trace('game-load:end')") < bootstrap.index("trace('boot:ready')")


def test_game_boot_failure_path_is_exercised_in_javascript_runtime():
    guard_path = STATIC / "game" / "task-payload-guard.js"
    bootstrap_path = STATIC / "game" / "game-bootstrap.js"
    script = f"""
const fs = require('fs');
global.window = global;
global.performance = {{ now: () => 10 }};
global.localStorage = {{
  getItem: key => key === 'devpilot-token' ? 'test-token' : (key === 'devpilot-build-game-project' ? 'old-project' : ''),
  setItem: () => {{}},
}};
const elements = new Map();
function element(id) {{
  if (!elements.has(id)) elements.set(id, {{ addEventListener: () => {{}}, showModal: () => {{}}, innerHTML: '' }});
  return elements.get(id);
}}
global.document = {{
  readyState: 'complete',
  getElementById: element,
  dispatchEvent: event => {{ global.__readyDispatched = event.type === 'devpilot:game:standalone-ready'; }},
  addEventListener: () => {{}},
}};
global.CustomEvent = class CustomEvent {{ constructor(type) {{ this.type = type; }} }};
global.fetch = async () => ({{ ok: true, status: 200 }});
global.api = async path => {{
  if (String(path).startsWith('/ui/projects?')) throw new Error('projects failed');
  return [];
}};
eval(fs.readFileSync({str(guard_path)!r}, 'utf8'));
global.loadBuildGame = async () => {{
  try {{ await global.api('/projects'); }} catch (_) {{}}
}};
eval(fs.readFileSync({str(bootstrap_path)!r}, 'utf8'));
setTimeout(() => {{
  const stages = (global.__devpilotGameBootTrace || []).map(item => item.stage);
  if (!stages.includes('projects:error')) process.exit(11);
  if (!stages.includes('boot:error')) process.exit(12);
  if (stages.includes('game-load:end')) process.exit(13);
  if (stages.includes('boot:ready')) process.exit(14);
  if (global.__readyDispatched) process.exit(15);
  process.exit(0);
}}, 25);
"""
    subprocess.run(["node", "-e", script], check=True, cwd=ROOT, timeout=5)


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
