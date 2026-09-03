from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_SWITCH = (ROOT / "app/static/game/project-switch.js").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_project_switch_is_loaded_after_objective_controls():
    assert "'game/project-switch.js'" in BOOTSTRAP
    assert BOOTSTRAP.index("'game/objective-controls.js'") < BOOTSTRAP.index("'game/project-switch.js'")
    assert "game-bootstrap.js?v=game-project-switch-v90-20260903" in INDEX


def test_active_round_exposes_mobile_safe_project_selector():
    assert "data-game90-project-switch" in PROJECT_SWITCH
    assert "Trocar projeto do Modo Jogo" in PROJECT_SWITCH
    assert ".game90-project-switch" in PROJECT_SWITCH
    assert "@media(max-width:520px)" in PROJECT_SWITCH
    assert "projectRows()" in PROJECT_SWITCH


def test_switch_reuses_canonical_project_context_without_stopping_old_round():
    assert "document.getElementById('build-game-project')" in PROJECT_SWITCH
    assert "canonical.dispatchEvent(new Event('change', {bubbles:true}))" in PROJECT_SWITCH
    assert "localStorage.setItem(PROJECT_KEY, targetProject)" in PROJECT_SWITCH
    assert "localStorage.removeItem(MISSION_KEY)" in PROJECT_SWITCH
    assert "Nenhuma tarefa é cancelada, apagada ou reiniciada" in PROJECT_SWITCH
    assert "/cancel" not in PROJECT_SWITCH
    assert "DELETE" not in PROJECT_SWITCH
    assert "reset()" not in PROJECT_SWITCH


def test_new_round_project_combo_can_return_to_existing_project_context():
    assert "[data-game73-project]" in PROJECT_SWITCH
    assert "document.addEventListener('change'" in PROJECT_SWITCH
    assert "switchProject(targetProject)" in PROJECT_SWITCH


def run_contract():
    test_project_switch_is_loaded_after_objective_controls()
    test_active_round_exposes_mobile_safe_project_selector()
    test_switch_reuses_canonical_project_context_without_stopping_old_round()
    test_new_round_project_combo_can_return_to_existing_project_context()
    print("GAME_PROJECT_SWITCH_V90=OK")


if __name__ == "__main__":
    run_contract()
