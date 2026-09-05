from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "app/static/build-game.js"
SUBPHASES = ROOT / "app/static/build-game-subphases.js"
PROJECT_BUILDER = ROOT / "app/static/project-builder.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_game_engine_keeps_seven_stage_contract() -> None:
    source = text(ENGINE)

    assert "id: 7" in source
    assert "name: 'Entrega e revisão'" in source
    assert "FASE: ${phase.id}/${phases.length}" in source
    assert "após as sete etapas" in source


def test_corrective_subphases_follow_all_seven_stages() -> None:
    source = text(SUBPHASES)

    assert "'Entrega e revisão'" in source
    assert "FASE: ${phaseId}/7" in source
    assert "phaseId <= 7" in source
    assert "phaseId <= 6" not in source
    assert "FASE: ${phaseId}/6" not in source


def test_new_project_is_ready_for_a_fresh_game_round() -> None:
    source = text(PROJECT_BUILDER)

    assert "const created = await request('/projects'" in source
    assert "prepareGame(created, description)" in source
    assert "localStorage.setItem(GAME_PROJECT_KEY, projectId)" in source
    assert "localStorage.setItem(GAME_DRAFT_PROJECT_KEY, projectId)" in source
    assert "localStorage.removeItem(GAME_MISSION_KEY)" in source
    assert "localStorage.setItem(GAME_DRAFT_GOAL_KEY, goal)" in source
    assert "criado e pronto para iniciar a esteira" in source
