from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "app/static/game/delivery-gate.js"
OBSERVER = ROOT / "app/static/game/stable-delivery-url.js"


def test_delivery_gate_starts_delivery_once_and_never_retries_in_browser():
    source = GATE.read_text(encoding="utf-8")

    assert source.count("/delivery/auto") == 1
    assert "scheduleDeliveryRetry" not in source
    assert "DELIVERY_RETRY_MS" not in source
    assert "DELIVERY_BLOCKED_RETRY_MS" not in source
    assert "deliveryStarted" in source
    assert "settledMissions" in source


def test_stable_delivery_url_is_passive_visible_only_observer():
    source = OBSERVER.read_text(encoding="utf-8")

    assert "WATCH_MS = 30000" in source
    assert "document.visibilityState" in source
    assert "/delivery/start" not in source
    assert "/delivery/retry" not in source
    assert "/delivery/validate-url" not in source
    assert "method: 'POST'" not in source
    assert "lastRenderSignature" in source
