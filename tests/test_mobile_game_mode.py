from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_game_mode_is_loaded_after_build_game():
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

    build_game = '<script src="/assets/build-game.js" defer></script>'
    mobile_game = '<script src="/assets/mobile-game-mode.js" defer></script>'

    assert build_game in main
    assert mobile_game in main
    assert main.index(build_game) < main.index(mobile_game)


def test_mobile_game_mode_adds_persistent_quickbar_button():
    script = (ROOT / "app" / "static" / "mobile-game-mode.js").read_text(encoding="utf-8")

    assert "mobile-route" in script
    assert 'data-view="build-game"' in script
    assert "mobile-quickbar" in script
    assert "mobile-game-mode-item" in script
    assert "Modo jogo" in script
    assert "🎮" in script
    assert "MutationObserver" in script
