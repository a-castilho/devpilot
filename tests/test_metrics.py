import json
from datetime import datetime, timedelta, timezone

from app.models import Run, Task, TaskStatus
from app.services.metrics import run_duration, run_usage, task_schedule


def test_run_metrics_use_persisted_codex_result():
    started = datetime(2026, 8, 16, 12, tzinfo=timezone.utc)
    run = Run(
        task_id="task",
        started_at=started,
        finished_at=started + timedelta(minutes=7, seconds=12),
        logs=json.dumps({"usage": {"input_tokens": 100, "output_tokens": 30, "total_tokens": 130}}),
    )

    assert run_duration(run) == 432
    assert run_usage(run)["total_tokens"] == 130


def test_schedule_respects_priority_and_reports_expected_completion():
    created = datetime(2026, 8, 16, 12, tzinfo=timezone.utc)
    low = Task(
        id="low",
        project_id="p",
        workspace_id="w",
        title="Low",
        prompt="Do low",
        priority=10,
        created_at=created,
        status=TaskStatus.queued,
    )
    high = Task(id="high", project_id="p", workspace_id="w", title="High", prompt="Do high", priority=90, created_at=created, status=TaskStatus.running)

    schedule = task_schedule([low, high], 600)

    assert schedule["high"]["expected_completion_at"] < schedule["low"]["expected_completion_at"]
    assert schedule["high"]["estimated_seconds"] == 600
