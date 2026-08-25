from pathlib import Path


STATIC = Path("app/static")


def test_mobile_game_shortcut_is_restored_without_booting_globally():
    source = (STATIC / "mobile-game-mode.js").read_text(encoding="utf-8")
    loader = (STATIC / "feature-loader.js").read_text(encoding="utf-8")

    assert "mobile-route" in source
    assert "mobile-quickbar" in source
    assert "mobile-game-mode-item" in source
    assert 'data-view="build-game"' in source
    assert "'mobile-game-mode.js'" in loader


def test_linux_training_stays_inside_session_workspace():
    source = (STATIC / "game-linux-training.js").read_text(encoding="utf-8")

    assert "TREINAMENTO 01 · SISTEMAS DA NAVE" in source
    assert "/api/linux/terminal/sessions" in source
    assert "find . -maxdepth 2" in source
    assert "~/" not in source
    assert "/home/" not in source
    assert "cd .." not in source
    assert "rm -" not in source
    assert "sudo " not in source


def test_voice_diagnostic_is_not_registered_as_weapon_shot():
    source = (STATIC / "game-weapons.js").read_text(encoding="utf-8")

    assert "voice-admin" not in source
    assert "Atualizar diagnóstico" not in source
    assert "devpilot.game.weaponShots.v1" not in source
    assert "DevPilotGameWeapons.registerShot" not in source
