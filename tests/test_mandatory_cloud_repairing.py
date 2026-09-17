from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECONCILER = (ROOT / "app/mandatory_cloud_reconciler.py").read_text(encoding="utf-8")


def test_repairing_delivery_remains_in_mandatory_reconciliation():
    assert '"repairing"' in RECONCILER.split("_ACTIVE_STATES =", 1)[1].split("}", 1)[0]
