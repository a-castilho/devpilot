from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def source(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_pilot_manual_is_completely_absent_from_critical_game_loader():
    loader = source("feature-loader.js")
    assert "game: ['game-shell.js', 'build-game.js']" in loader
    assert "build-game-pilot-manual.js" not in loader
    assert "gameManual" not in loader
    assert "requestGameManual" not in loader


def test_pilot_manual_is_frontend_only_and_does_not_call_backend():
    manual = source("build-game-pilot-manual.js")
    assert "fetch(" not in manual
    assert "gameApi(" not in manual
    assert "api(" not in manual
    assert "/api/" not in manual


def test_pilot_manual_button_and_dialog_contract_are_present():
    manual = source("build-game-pilot-manual.js")
    assert "data-pilot-manual-open" in manual
    assert "Manual do Piloto" in manual
    assert 'role=\"dialog\"' in manual
    assert 'aria-modal=\"true\"' in manual
    assert "data-pilot-manual-close" in manual
    assert "event.key === 'Escape'" in manual


def test_pilot_manual_documents_real_execution_invariants():
    manual = source("build-game-pilot-manual.js")
    assert "um clique deve produzir no máximo uma execução" in manual
    assert "Animação nunca confirma sucesso" in manual
    assert "Permissões reais continuam sendo responsabilidade do backend" in manual


def test_pilot_manual_mount_is_idempotent():
    manual = source("build-game-pilot-manual.js")
    assert "window.__devpilotBuildGamePilotManualReady" in manual
    assert "hud.querySelector('[data-pilot-manual-open]')" in manual
    assert "document.getElementById(MODAL_ID)" in manual
