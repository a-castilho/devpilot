from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
RECOVERY = (ROOT / "app/static/game/recovery-runtime.js").read_text(encoding="utf-8")


def test_game_assets_use_current_v88_revision():
    assert 'game-flow-v88-20260903' in INDEX
    assert "const ASSET_REVISION = 'game-flow-v88-20260903'" in BOOTSTRAP
    assert "window.__devpilotGameBootProfile='unified-v88'" in BOOTSTRAP


def test_archived_runtime_bypasses_failure_recovery():
    assert "orchestratorState" in RECOVERY
    assert "runtimeState === 'archived'" in RECOVERY
    assert "runtimeState === 'canceled'" in RECOVERY
    assert "runtimeState === 'cancel_requested'" in RECOVERY
    assert "return originalRetry();" in RECOVERY


def run_contract():
    test_game_assets_use_current_v88_revision()
    test_archived_runtime_bypasses_failure_recovery()
    print("GAME_V88_REVISION=OK")


if __name__ == "__main__":
    run_contract()
