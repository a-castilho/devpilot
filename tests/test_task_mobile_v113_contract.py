from pathlib import Path


def test_hidden_game_rows_override_mobile_card_display():
    css = Path("app/static/task-development-v2.css").read_text(encoding="utf-8")
    assert "tr.task-main-row[hidden]" in css
    assert "tr.tasks-v9-row[hidden]" in css
    assert "task-main-row[hidden] + tr.task-details-row" in css
    assert "display:none!important" in css


def test_orchestrator_is_the_only_mobile_action_grid():
    css = Path("app/static/task-development-v2.css").read_text(encoding="utf-8")
    assert ".tasks-v9-actions:has(.task-orchestrator-actions)" in css
    assert "display:block!important" in css
    assert ".task-orchestrator-actions" in css
    assert "grid-template-columns:repeat(2,minmax(0,1fr))!important" in css
    assert "grid-template-columns:minmax(0,1fr)!important" in css
    assert "white-space:normal!important" in css
    assert "position:static!important" in css


def test_pipeline_v2_contract_is_preserved():
    game = Path("app/static/build-game.js").read_text(encoding="utf-8")
    assert "DEVPILOT_BUILD_GAME_PIPELINE_V2" in game
    assert "Planejamento" in game
    assert "Entrega e revisão" in game
