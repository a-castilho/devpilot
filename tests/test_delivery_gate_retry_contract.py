from pathlib import Path


DELIVERY_GATE = Path("app/static/game/delivery-gate.js")


def test_blocked_delivery_is_rechecked_instead_of_becoming_terminal():
    source = DELIVERY_GATE.read_text(encoding="utf-8")
    assert "DELIVERY_BLOCKED_RETRY_MS" in source
    assert "if (currentStatus === 'blocked') return false" not in source
    assert "scheduleDeliveryRetry(DELIVERY_BLOCKED_RETRY_MS)" in source
    assert "/delivery/auto" in source
