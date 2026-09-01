from pathlib import Path

INDEX = Path("app/static/game/index.html").read_text(encoding="utf-8")
SOURCE = Path("app/static/game/start-round-mobile.js").read_text(encoding="utf-8")


def test_game_loads_explicit_start_round_recovery_with_fresh_cache_key():
    assert "game/start-round-mobile.js?v=frontend-v53-game-start" in INDEX
    assert "objective-controls.js?v=frontend-v53-game-start" in INDEX
    assert "build-game.js?v=frontend-v53-game-start" in INDEX


def test_initial_round_relabels_new_round_as_start_game():
    assert "button.textContent = initial ? 'Iniciar jogo' : 'Nova rodada'" in SOURCE
    assert "data-play-phase" in SOURCE
    assert "build-game-goal" in SOURCE


def test_start_requires_goal_and_delegates_to_real_phase_button():
    assert "Descreva a entrega da rodada para iniciar o jogo" in SOURCE
    assert "phaseButton.click()" in SOURCE
    assert "stopImmediatePropagation" in SOURCE
