from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_HTML = ROOT / "app/static/game/index.html"
BOOTSTRAP_JS = ROOT / "app/static/game/game-bootstrap.js"
OBJECTIVE_JS = ROOT / "app/static/game/objective-controls.js"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_standalone_loads_quick_start_after_action_runtime():
    html = source(GAME_HTML)
    bootstrap = source(BOOTSTRAP_JS)

    assert "/assets/build-game.js" in html
    assert "game/objective-controls.js" in bootstrap
    assert bootstrap.index("game/action-runtime.js") < bootstrap.index("game/objective-controls.js")


def test_quick_start_exposes_project_delivery_and_one_primary_action():
    js = source(OBJECTIVE_JS)

    assert "Escolha o projeto" in js
    assert "Entrega da rodada" in js
    assert "🚀 Criar e jogar" in js
    assert "Escolha o projeto, descreva a entrega e comece. É só isso." in js
    assert "Salvar objetivo" not in js
    assert "Salvar e iniciar fase" not in js


def test_quick_start_delegates_to_existing_real_runtime():
    js = source(OBJECTIVE_JS)

    assert "#build-game-project" in js
    assert "#build-game-goal" in js
    assert "[data-play-phase]" in js
    assert "phaseButton.click()" in js
    assert "window.loadBuildGame" in js
    assert "dispatchEvent(new Event('input'" in js
    assert "dispatchEvent(new Event('change'" in js


def test_quick_start_is_event_driven_without_dom_observer():
    js = source(OBJECTIVE_JS)

    assert "devpilot-simple-game:not(.devpilot-game-started)" in js
    assert "devpilot-game-started:not(.devpilot-game-details)" in js
    assert "build-game-phase:not(.current)" in js
    assert "Ver detalhes" in js
    assert "MutationObserver" not in js
    assert "devpilot:game:rendered" in js


def test_quick_start_validates_project_and_delivery():
    js = source(OBJECTIVE_JS)

    assert "Escolha um projeto para jogar" in js
    assert "Conte em uma frase o que você quer receber nesta rodada" in js
    assert "if (!persistGoal(view, textarea)) return false;" in js


def test_simple_game_cache_revision_is_fresh():
    revision = "release-1.2.0-game-entry-stable-v64-20260902"
    assert revision in source(GAME_HTML)
    assert revision in source(BOOTSTRAP_JS)
