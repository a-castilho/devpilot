from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY_JS = ROOT / "app" / "static" / "game-entry.js"
ENTRY_CSS = ROOT / "app" / "static" / "game-entry.css"
MOBILE_JS = ROOT / "app" / "static" / "mobile-accordion-menu.js"
SHELL_JS = ROOT / "app" / "static" / "game-shell.js"


def test_mobile_shell_loads_visible_game_entry():
    js = MOBILE_JS.read_text(encoding="utf-8")
    assert "ensureGameEntry" in js
    assert "/assets/game-entry.js?v=20260825-1" in js
    assert "data-game-entry" in js


def test_overview_has_clear_game_call_to_action_contract():
    js = ENTRY_JS.read_text(encoding="utf-8")
    assert "#overview-view" in js
    assert "MODO JOGO · DESENVOLVIMENTO REAL" in js
    assert "Construa software como uma missão." in js
    assert "Jogar agora" in js
    assert "Continuar partida" in js
    assert "data-open-game-entry" in js


def test_game_entry_keeps_game_bundle_lazy_and_uses_response_manager():
    js = ENTRY_JS.read_text(encoding="utf-8")
    assert "window.__devpilotLoadFeature?.('game')" in js
    assert "window.DevPilotResponses?.loading" in js
    assert "window.DevPilotResponses?.success" in js
    assert "window.DevPilotResponses?.error" in js


def test_game_entry_explicitly_hands_off_to_game_shell():
    entry = ENTRY_JS.read_text(encoding="utf-8")
    shell = SHELL_JS.read_text(encoding="utf-8")
    assert "window.DevPilotGameShell?.enter?.(document.getElementById('build-game-view'))" in entry
    assert "window.DevPilotGameShell = Object.freeze" in shell
    assert "enter: enterGame" in shell
    assert "exit: exitGame" in shell
    assert "sync," in shell


def test_game_entry_visual_is_large_but_bounded_on_mobile():
    css = ENTRY_CSS.read_text(encoding="utf-8")
    assert "33.333vw" in css
    assert "min-height:104px" in css
    assert "@media(max-width:520px)" in css
    assert "grid-template-columns:minmax(0,1fr) 33.333vw" in css
