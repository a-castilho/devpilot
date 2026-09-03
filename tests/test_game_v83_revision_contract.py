from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
RECOVERY = (ROOT / "app/static/game/recovery-runtime.js").read_text(encoding="utf-8")


def test_game_assets_use_one_revision():
    assert 'game-flow-v83-20260903' in INDEX
    assert "const ASSET_REVISION = 'game-flow-v83-20260903'" in BOOTSTRAP
    assert "window.__devpilotGameBootProfile = 'unified-v83'" in BOOTSTRAP


def test_archived_runtime_bypasses_failure_recovery():
    assert "runtimeState === 'archived'" in RECOVERY
    assert "runtimeState === 'canceled'" in RECOVERY
    assert "return originalRetry();" in RECOVERY
    assert "tasks.status is still queued" in RECOVERY


def run_contract():
    test_game_assets_use_one_revision()
    test_archived_runtime_bypasses_failure_recovery()
    print("GAME_V83_REVISION=OK")


if __name__ == "__main__":
    run_contract()
