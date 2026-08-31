from pathlib import Path


BUILD_GAME_COCKPIT_JS = Path("app/static/build-game-cockpit.js")


def test_blank_game_objective_is_rejected_before_play_handler_runs():
    source = BUILD_GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "function ensurePlayableGoal(button)" in source
    assert "#build-game-view [data-play-phase]" in source
    assert "document.addEventListener('click'" in source
    assert "}, true);" in source
    assert "if (!view || !input || String(input.value || '').trim()) return true;" in source
    assert "input.focus()" in source
    assert "O jogo não inventa o objetivo" in source


def test_game_goal_must_come_from_user_without_automatic_fallback():
    source = BUILD_GAME_COCKPIT_JS.read_text(encoding="utf-8")

    assert "function automaticGoal" not in source
    assert "input.value = automaticGoal(view)" not in source
    assert "Objetivo definido automaticamente" not in source
    assert "Descreva o que deve ser entregue nesta rodada" in source
