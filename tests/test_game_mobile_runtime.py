from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "app/static/game/runtime.js"
GAME = ROOT / "app/static/build-game.js"


def test_standalone_runtime_bounds_game_task_payload():
    runtime = RUNTIME.read_text(encoding="utf-8")
    game = GAME.read_text(encoding="utf-8")

    assert "const GAME_TASK_LIMIT = 80;" in runtime
    assert "normalizeGamePath" in runtime
    assert "params.set('limit', String(GAME_TASK_LIMIT))" in runtime
    assert "limit=500" in game  # legacy request is clamped by the standalone runtime


def test_standalone_runtime_deduplicates_gets_and_times_out():
    runtime = RUNTIME.read_text(encoding="utf-8")

    assert "const inflightGets = new Map();" in runtime
    assert "inflightGets.has(key)" in runtime
    assert "const API_TIMEOUT_MS = 15000;" in runtime
    assert "controller.abort()" in runtime
    assert "Servidor demorou para responder" in runtime
