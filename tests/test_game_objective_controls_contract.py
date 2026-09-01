from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_HTML = ROOT / "app/static/game/index.html"
OBJECTIVE_JS = ROOT / "app/static/game/objective-controls.js"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_standalone_loads_objective_controls_after_build_game_runtime():
    html = source(GAME_HTML)
    build_pos = html.index('/assets/build-game.js?v=frontend-v31')
    controls_pos = html.index('/assets/game/objective-controls.js?v=frontend-v49')
    bootstrap_pos = html.index('/assets/game/game-bootstrap.js?v=frontend-v31')

    assert build_pos < controls_pos < bootstrap_pos


def test_objective_controls_expose_required_game_actions():
    js = source(OBJECTIVE_JS)

    assert 'OBJETIVO DA PARTIDA' in js
    assert 'Salvar e iniciar fase' in js
    assert 'Salvar objetivo' in js
    assert 'Nova partida' in js
    assert 'Atualizar' in js


def test_objective_controls_delegate_to_existing_runtime_contract():
    js = source(OBJECTIVE_JS)

    assert "#build-game-goal" in js
    assert "#build-game-new" in js
    assert "[data-play-phase]" in js
    assert "window.loadBuildGame" in js
    assert "dispatchEvent(new Event('input'" in js
    assert "dispatchEvent(new Event('change'" in js


def test_objective_requires_non_empty_value_before_starting_phase():
    js = source(OBJECTIVE_JS)

    assert "Defina o objetivo da partida antes de continuar" in js
    assert "if (!persistGoal(view, textarea)) return;" in js
