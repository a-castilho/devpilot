from datetime import datetime, timedelta, timezone

from app.delivery_cloud_bridge import _trial_cloud_entitled


def _entitlements(workspace_id="tenant-a", **overrides):
    entitlement = {
        "status": "active",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    entitlement.update(overrides)
    return {workspace_id: entitlement}


def test_trial_cloud_entitlement_requires_explicit_active_workspace():
    assert _trial_cloud_entitled("tenant-a", _entitlements()) is True
    assert _trial_cloud_entitled("tenant-b", _entitlements()) is False
    assert _trial_cloud_entitled("tenant-a", {}) is False
    assert _trial_cloud_entitled("tenant-a", _entitlements(status="suspended")) is False
    assert _trial_cloud_entitled("tenant-a", _entitlements(status="paid")) is False


def test_trial_cloud_entitlement_rejects_expired_or_invalid_expiry():
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert _trial_cloud_entitled("tenant-a", _entitlements(expires_at=expired)) is False
    assert _trial_cloud_entitled("tenant-a", _entitlements(expires_at="invalid")) is False
    assert _trial_cloud_entitled("tenant-a", _entitlements(expires_at="")) is False
