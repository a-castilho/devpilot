from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "app" / "static" / "feature-loader.js"
GAME_HTML = ROOT / "app" / "static" / "game" / "index.html"
SHELL_JS = ROOT / "app" / "static" / "game-shell.js"
SHELL_CSS = ROOT / "app" / "static" / "game-shell.css"
BUILD_GAME = ROOT / "app" / "static" / "build-game.js"


def test_standalone_game_document_loads_engine_without_dashboard_shell_bundle():
    loader = LOADER.read_text(encoding="utf-8")
    html = GAME_HTML.read_text(encoding="utf-8")
    assert "'game-shell.js'" not in loader
    assert "'build-game.js'" not in loader
    assert "game: [" not in loader
    assert '/assets/build-game.js' in html
    assert '/assets/game/game-bootstrap.js' in html
    assert '/assets/feature-loader.js' not in html


def test_game_shell_moves_game_view_into_dedicated_stage_and_restores_it():
    js = SHELL_JS.read_text(encoding="utf-8")
    assert "devpilot-game-shell" in js
    assert "data-game-slot" in js
    assert "slot.appendChild(view)" in js
    assert "restoreView(view)" in js
    assert "originalParent" in js
    assert "originalNextSibling" in js


def test_game_shell_has_single_authoritative_mode_class_and_hud():
    js = SHELL_JS.read_text(encoding="utf-8")
    assert "document.body.classList.add('devpilot-game-mode')" in js
    assert "document.body.classList.remove('devpilot-game-mode')" in js
    for marker in ("data-game-hud-phase", "data-game-hud-project", "data-game-hud-xp", "data-game-hud-progress"):
        assert marker in js


def test_game_shell_exposes_event_bus_and_feedback_bridge():
    js = SHELL_JS.read_text(encoding="utf-8")
    assert "window.DevPilotGameEvents" in js
    assert "devpilot:game:" in js
    assert "phase-start-requested" in js
    assert "new-session-requested" in js
    assert "window.DevPilotResponses?.loading" in js
    assert "window.DevPilotResponses?.info" in js


def test_game_shell_is_mobile_first_and_does_not_reuse_dashboard_navigation():
    css = SHELL_CSS.read_text(encoding="utf-8")
    assert "position:fixed;inset:0" in css
    assert "@media(max-width:900px)" in css
    assert "env(safe-area-inset-top)" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "min-height:56px" in css
    assert "body.devpilot-game-mode" in css


def test_existing_build_game_remains_real_task_backed():
    js = BUILD_GAME.read_text(encoding="utf-8")
    assert "[DEVPILOT_BUILD_GAME_V1]" in js
    assert "await api('/tasks'" in js
    assert "requires_approval: false" in js
    assert "git diff --stat" in js
    assert "showView('build-game')" in js
