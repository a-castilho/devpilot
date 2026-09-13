from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.services.delivery_stall_recovery import (
    MAX_QUEUE_NUDGES_PER_ATTEMPT,
    QUEUED_STALL_SECONDS,
    _age_seconds,
    _stall_count,
)


ROOT = Path(__file__).resolve().parents[1]


def test_delivery_stall_threshold_is_bounded_and_operational():
    assert 60 <= QUEUED_STALL_SECONDS <= 300
    assert 1 <= MAX_QUEUE_NUDGES_PER_ATTEMPT <= 3


def test_delivery_stall_age_accepts_naive_and_aware_datetimes():
    aware = datetime.now(timezone.utc) - timedelta(seconds=180)
    naive = aware.replace(tzinfo=None)

    assert _age_seconds(aware) >= 170
    assert _age_seconds(naive) >= 170
    assert _age_seconds(None) == float("inf")


def test_delivery_stall_markers_are_persisted_in_task_prompt():
    task = SimpleNamespace(
        prompt=(
            "[DEVPILOT_DELIVERY_REPAIR_V1]\n"
            "[delivery-stall-recovery:1]\n"
            "[delivery-stall-recovery:2]\n"
        )
    )
    assert _stall_count(task) == 2


def test_exhausted_repair_lifecycle_is_explicitly_bounded():
    source = (ROOT / "app/services/delivery_stall_recovery.py").read_text(encoding="utf-8")

    assert "existing.status in {TaskStatus.failed, TaskStatus.blocked}" in source
    assert "guard._retry_count(existing) >= guard.MAX_SAFE_RETRIES" in source
    assert "return existing, False" in source
    assert "project.delivery_repair_stall_requeued" in source
    assert "project.delivery_repair_stall_failed" in source
