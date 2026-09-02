from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY_JS = ROOT / "app" / "static" / "game-entry.js"
ENTRY_CSS = ROOT / "app" / "static" / "game-entry.css"
MOBILE_JS = ROOT / "app" / "static" / "mobile-accordion-menu.js"
FEATURE_LOADER_JS = ROOT / "app" / "static" / "feature-loader.js"
GAME_HTML = ROOT / "app" / "static" / "game" / "index.html"


def test_mobile_shell_exposes_direct_game_action():
    js = MOBILE_JS.read_text(encoding="utf-8")
    assert "window.__devpilotMobileAccordionMenuStable" in js
    assert "data-simple-game" in js
    assert "<small>Jogo</small>" in js
    assert "window.location.assign('/game/index.html')" in js
    assert "ensureGameShipsRuntime" in js


def test_overview_has_clear_game_call_to_action_contract():
    js = ENTRY_JS.read_text(encoding="utf-8")
    assert "#overview-view" in js
    assert "MODO JOGO · DESENVOLVIMENTO REAL" in js
    assert "Construa software como uma missão." in js
    assert "Jogar agora" in js
    assert "Continuar partida" in js
    assert "data-open-game-entry" in js


def test_game_entry_navigates_to_isolated_document_and_keeps_response_feedback():
    js = ENTRY_JS.read_text(encoding="utf-8")
    loader = FEATURE_LOADER_JS.read_text(encoding="utf-8")
    html = GAME_HTML.read_text(encoding="utf-8")

    assert "const GAME_URL = '/game/index.html'" in js
    assert "window.location.assign(GAME_URL)" in js
    assert "window.__devpilotLoadFeature?.('game')" not in js
    assert "game: ['game-shell.js', 'build-game.js']" not in loader
    assert '/assets/build-game.js' in html
    assert "window.DevPilotResponses?.loading" in js
    assert "window.DevPilotResponses?.success" in js
    assert "window.DevPilotResponses?.error" in js


def test_game_entry_does_not_handoff_to_dashboard_game_shell():
    entry = ENTRY_JS.read_text(encoding="utf-8")
    assert "window.DevPilotGameShell?.enter?." not in entry
    assert "window.location.assign(GAME_URL)" in entry


def test_game_entry_visual_is_large_but_bounded_on_mobile():
    css = ENTRY_CSS.read_text(encoding="utf-8")
    assert "33.333vw" in css
    assert "min-height:104px" in css
    assert "@media(max-width:520px)" in css
    assert "grid-template-columns:minmax(0,1fr) 33.333vw" in css
