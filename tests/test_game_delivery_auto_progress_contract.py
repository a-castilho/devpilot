from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / "app/static/game/game-bootstrap.js"
AUTO = ROOT / "app/static/game/delivery-auto-progress.js"


def test_legacy_auto_progress_is_not_loaded():
    boot = BOOT.read_text(encoding="utf-8")
    assert "game/delivery-auto-progress.js" not in boot
    assert "game/stable-delivery-url.js" in boot
    assert "game/delivery-gate.js" in boot


def test_legacy_auto_progress_cannot_mutate_delivery():
    source = AUTO.read_text(encoding="utf-8")
    assert "/delivery/auto" not in source
    assert "method: 'POST'" not in source
    assert "__devpilotDeliveryAutoProgressReady" in source
