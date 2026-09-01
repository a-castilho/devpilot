from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
OBJECTIVE = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")
BUILD_GAME = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")


def test_standalone_game_uses_one_asset_revision() -> None:
    revision = "full-20260901-v52"
    assert INDEX.count(f"?v={revision}") == 11
    assert 'data-devpilot-game-build="full-20260901-v52"' in INDEX
    assert '/assets/game/objective-controls.js?v=full-20260901-v52' in INDEX
    assert '/assets/game/pipeline-v2-compat.js?v=full-20260901-v52' in INDEX
    assert '/assets/game/game-bootstrap.js?v=full-20260901-v52' in INDEX


def test_full_game_keeps_v2_pipeline_and_objective_controls() -> None:
    assert 'OBJETIVO DA PARTIDA' in OBJECTIVE
    assert 'Salvar e iniciar fase' in OBJECTIVE
    assert 'Salvar objetivo' in OBJECTIVE
    assert 'Nova partida' in OBJECTIVE
    assert 'Atualizar' in OBJECTIVE
    assert '0/7 etapas' in BUILD_GAME
