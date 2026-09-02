from pathlib import Path

INDEX = Path("app/static/game/index.html").read_text(encoding="utf-8")
BOOT = Path("app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
UI = Path("app/static/game/objective-controls.js").read_text(encoding="utf-8")
BUILD = Path("app/static/build-game.js").read_text(encoding="utf-8")


def test_start_round_helper_is_replaced_by_unified_ui():
    assert "game/start-round-mobile.js" not in INDEX
    assert "'game/start-round-mobile.js'" not in BOOT
    assert "'game/objective-controls.js'" in BOOT
    assert "data-game73-start" in UI
    assert "🚀 Jogar agora" in UI


def test_initial_round_calls_real_controller_directly():
    assert "await engine.startRound({projectId, goal});" in UI
    assert "phaseButton.click()" not in UI
    assert "data-play-phase" not in UI
    assert "window.__devpilotGameControllerV73" in BUILD


def test_start_validates_project_and_goal_in_engine():
    assert "if (!targetProject) throw new Error('Escolha um projeto')" in BUILD
    assert "if (!targetGoal) throw new Error('Descreva a entrega da rodada')" in BUILD
    assert "await createPhaseTask(1, targetGoal, {force:true});" in BUILD
