from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Run, Task, TaskStatus


DEFAULT_ESTIMATE_SECONDS = 30 * 60


def run_duration(run: Run) -> int | None:
    if not run.finished_at:
        return None
    return max(0, int((run.finished_at - run.started_at).total_seconds()))


def run_usage(run: Run) -> dict[str, int]:
    try:
        result = json.loads(run.logs or "{}")
    except json.JSONDecodeError:
        result = {}
    usage = result.get("usage", {}) if isinstance(result, dict) else {}
    return {
        "input_tokens": int(usage.get("input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "cached_input_tokens": int(usage.get("cached_input_tokens", 0)),
        "total_tokens": int(usage.get("total_tokens", 0)),
    }


def workspace_metrics(db: Session, workspace_id: str) -> dict[str, object]:
    runs = db.scalars(
        select(Run).join(Task, Run.task_id == Task.id).where(Task.workspace_id == workspace_id)
    ).all()
    durations = [duration for run in runs if (duration := run_duration(run)) is not None]
    average = int(sum(durations) / len(durations)) if durations else DEFAULT_ESTIMATE_SECONDS
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0, "total_tokens": 0}
    for run in runs:
        current = run_usage(run)
        for key in usage:
            usage[key] += current[key]
    active = db.scalars(
        select(Task)
        .where(
            Task.workspace_id == workspace_id,
            Task.status.in_([TaskStatus.queued, TaskStatus.running]),
        )
        .order_by(Task.priority.desc(), Task.created_at)
    ).all()
    return {
        "average_duration_seconds": average,
        "queue_eta_seconds": average * len(active),
        "usage": usage,
    }


def task_schedule(tasks: list[Task], average_seconds: int) -> dict[str, dict[str, object]]:
    active = sorted(
        (task for task in tasks if task.status in {TaskStatus.queued, TaskStatus.running}),
        key=lambda task: (-task.priority, task.created_at),
    )
    now = datetime.now(timezone.utc)
    schedule: dict[str, dict[str, object]] = {}
    elapsed = 0
    for task in active:
        elapsed += average_seconds
        schedule[task.id] = {
            "estimated_seconds": average_seconds,
            "expected_completion_at": (now + timedelta(seconds=elapsed)).isoformat(),
        }
    return schedule
