from pathlib import Path

INDEX = Path("app/static/game/index.html").read_text(encoding="utf-8")
SOURCE = Path("app/static/game/start-round-mobile.js").read_text(encoding="utf-8")


def test_game_loads_round_launcher_v54_with_fresh_cache_key():
    assert "game/start-round-mobile.js?v=game-v54-round-launch-20260901" in INDEX
    assert "build-game.js?v=game-v54-round-launch-20260901" in INDEX
    assert INDEX.index("/assets/build-game.js") < INDEX.index("/assets/game/start-round-mobile.js")


def test_round_launcher_is_unambiguous_for_initial_and_historical_rounds():
    assert "▶ Iniciar rodada" in SOURCE
    assert "hasRoundHistory" in SOURCE
    assert "firstPlayable" in SOURCE
    assert "data-play-phase" in SOURCE


def test_round_launcher_requires_goal_and_starts_real_phase():
    assert "Descreva a entrega da rodada para iniciar o jogo" in SOURCE
    assert "fresh.playable.click()" in SOURCE
    assert "playable.click()" in SOURCE
    assert "stopImmediatePropagation" in SOURCE


def test_historical_round_resets_and_restores_goal_before_starting():
    assert "previousMission" in SOURCE
    assert "window.confirm = () => true" in SOURCE
    assert "waitForFreshRound" in SOURCE
    assert "syncGoal(fresh.goal, value)" in SOURCE
