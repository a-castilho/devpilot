from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "app" / "delivery_url_recovery.py"
GATE = ROOT / "app" / "static" / "game" / "delivery-gate.js"
BLOCKED = ROOT / "app" / "static" / "game" / "delivery-blocked-recovery.js"
OBSERVER = ROOT / "app" / "static" / "game" / "stable-delivery-url.js"


def test_backend_reconciles_failed_blocked_and_waiting_url_states():
    source = RECOVERY.read_text(encoding="utf-8")
    assert '"blocked", "failed"' in source
    assert '_RECOVERABLE_GATES = {"waiting_for_testable_url"}' in source
    assert 'recovery_next_at' in source
    assert 'recovery_last_attempt_at' in source
    assert '_BLOCKED_RECOVERY_DELAY_SECONDS = 60' in source
    assert '_FAILED_RECOVERY_DELAY_SECONDS = 90' in source
    assert 'delivery.run_delivery(db, project, "delivery-reconciler")' in source
    assert 'project.delivery_recovery_completed' in source
    assert 'project.delivery_recovery_retry_scheduled' in source


def test_browser_only_starts_delivery_and_does_not_own_retries():
    gate = GATE.read_text(encoding="utf-8")
    blocked = BLOCKED.read_text(encoding="utf-8")
    observer = OBSERVER.read_text(encoding="utf-8")

    assert gate.count("/delivery/auto") == 1
    assert "scheduleDeliveryRetry" not in gate
    assert "DELIVERY_RETRY_MS" not in gate
    assert "deliveryStarted" in gate

    assert "method: 'POST'" not in blocked
    assert "/retry" not in blocked

    assert "WATCH_MS = 15000" in observer
    assert "const call = async path" in observer
    assert "method: 'POST'" not in observer
