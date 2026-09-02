from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_game_v73_validation_marker_tracks_unified_runtime():
    build = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")
    ui = (ROOT / "app/static/game/objective-controls.js").read_text(encoding="utf-8")
    index = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")

    assert "__devpilotGameControllerV73" in build
    assert "__devpilotGameUiV73Ready" in ui
    assert "data-game-nonblocking-entry-v67" not in index
