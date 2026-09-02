from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_HTML = ROOT / "app/static/game/index.html"
BOOTSTRAP_JS = ROOT / "app/static/game/game-bootstrap.js"
OBJECTIVE_JS = ROOT / "app/static/game/objective-controls.js"
BUILD_GAME_JS = ROOT / "app/static/build-game.js"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_standalone_loads_simple_ui_after_real_core():
    html = source(GAME_HTML)
    bootstrap = source(BOOTSTRAP_JS)

    assert "/assets/build-game.js" in html
    assert "game/objective-controls.js" in bootstrap
    assert "game/action-runtime.js" not in bootstrap
    assert bootstrap.index("await withTimeout(window.loadBuildGame()") < bootstrap.index("startEnhancements();")


def test_simple_ui_exposes_project_delivery_and_one_primary_action():
    js = source(OBJECTIVE_JS)

    assert "Projeto" in js
    assert "Entrega da rodada" in js
    assert "🚀 Jogar agora" in js
    assert "Escolha o projeto, descreva o resultado e toque uma única vez em Jogar agora." in js
    assert "Salvar objetivo" not in js
    assert "Salvar e iniciar fase" not in js


def test_simple_ui_calls_real_controller_without_hidden_phase_click():
    js = source(OBJECTIVE_JS)
    build = source(BUILD_GAME_JS)

    assert "window.__devpilotGameControllerV73" in build
    assert "await engine.startRound({projectId, goal});" in js
    assert "phaseButton.click()" not in js
    assert "[data-play-phase]" not in js
    assert "__devpilotGameControllerV73" in build


def test_simple_ui_is_event_driven_without_dom_observer():
    js = source(OBJECTIVE_JS)

    assert "devpilot-game-v73-shell" in js
    assert "show-details" in js
    assert "Detalhes" in js
    assert "MutationObserver" not in js
    assert "devpilot:game:rendered" in js
    assert "devpilot:game:state" in js


def test_simple_ui_surfaces_validation_and_runtime_errors():
    js = source(OBJECTIVE_JS)

    assert "Falha ao iniciar a rodada" in js
    assert "game73-error" in js
    assert "try {" in js
    assert "catch (error)" in js


def test_simple_game_cache_revision_is_fresh():
    revision = "game-unified-v73-20260902"
    assert revision in source(GAME_HTML)
    assert revision in source(BOOTSTRAP_JS)
