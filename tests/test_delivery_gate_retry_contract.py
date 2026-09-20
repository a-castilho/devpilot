from pathlib import Path


DELIVERY_GATE = Path("app/static/game/delivery-gate.js")


def test_blocked_delivery_is_owned_by_backend_worker():
    source = DELIVERY_GATE.read_text(encoding="utf-8")
    assert "/delivery/auto" not in source
    assert "scheduleDeliveryRetry" not in source
    assert "observeAutomaticDelivery" in source
    assert "settledMissions" in source
    assert "devpilot:delivery:updated" in source
