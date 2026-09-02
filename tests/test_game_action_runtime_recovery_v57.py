from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = (ROOT / "app/static/game/action-runtime.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")


def test_action_runtime_serializes_renders_and_blocks_fast_duplicate_taps():
    assert "if (loadInFlight)" in ACTION
    assert "loadRequested = true" in ACTION
    assert "now - previous < 650" in ACTION
    assert "event.stopImmediatePropagation()" in ACTION
    assert "__devpilotGameRunAction" in ACTION
    assert "devpilot:game:rendered" in ACTION


def test_boot_requires_action_runtime_before_first_build_game_render():
    assert "const REQUIRED_ASSET = 'game/action-runtime.js'" in BOOT
    assert "await loadAsset(REQUIRED_ASSET, REQUIRED_TIMEOUT_MS)" in BOOT
    assert "__devpilotGameActionRuntimeReady" in BOOT
    assert "Coordenador de ações do Modo Jogo indisponível" in BOOT
    assert BOOT.index("await loadAsset(REQUIRED_ASSET") < BOOT.index("await withTimeout(window.loadBuildGame()")


def test_standalone_assets_have_recovery_cache_revision():
    revision = "release-1.2.0-game-recovery-v57-20260902"
    assert revision in INDEX
    assert revision in BOOT
    assert INDEX.count(revision) >= 5
