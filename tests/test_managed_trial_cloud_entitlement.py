from datetime import datetime, timedelta, timezone
import json

from app.delivery_cloud_bridge import _trial_cloud_entitled


class WorkspaceStub:
    def __init__(self, settings):
        self.settings_json = json.dumps(settings) if settings is not None else None


def _active_entitlement(**overrides):
    entitlement = {
        "eligible": True,
        "status": "active",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    entitlement.update(overrides)
    return {"managed_trial_clouds": entitlement}


def test_trial_cloud_entitlement_requires_explicit_active_eligibility():
    assert _trial_cloud_entitled(WorkspaceStub(_active_entitlement())) is True
    assert _trial_cloud_entitled(WorkspaceStub(None)) is False
    assert _trial_cloud_entitled(WorkspaceStub({})) is False
    assert _trial_cloud_entitled(WorkspaceStub(_active_entitlement(eligible=False))) is False
    assert _trial_cloud_entitled(WorkspaceStub(_active_entitlement(status="suspended"))) is False


def test_trial_cloud_entitlement_rejects_expired_or_invalid_expiry():
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert _trial_cloud_entitled(WorkspaceStub(_active_entitlement(expires_at=expired))) is False
    assert _trial_cloud_entitled(WorkspaceStub(_active_entitlement(expires_at="invalid"))) is False
    assert _trial_cloud_entitled(WorkspaceStub(_active_entitlement(expires_at=""))) is False
