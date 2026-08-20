from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Run, Task, TaskStatus, Workspace
from app.security import require_access


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\"']+"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


def _workspace_id(db: Session) -> str:
    workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == "default"))
    if not workspace_id:
        raise HTTPException(404, "Workspace not found")
    return workspace_id


def sanitize_text(value: str) -> str:
    text = str(value or "")
    text = _SECRET_PATTERNS[0].sub(r"\1[REDACTED]", text)
    for pattern in _SECRET_PATTERNS[1:]:
        text = pattern.sub("[REDACTED]", text)
    return text


def sanitize_payload(value):
    if isinstance(value, dict):
        return {key: sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def _logs_payload(run: Run | None):
    if not run or not run.logs:
        return {}
    try:
        return json.loads(run.logs)
    except (TypeError, ValueError):
        return {"raw": run.logs}


def _last_nonempty_line(value: str, limit: int = 700) -> str:
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    return sanitize_text(lines[-1])[:limit] if lines else ""


def failure_reason(run: Run | None) -> str:
    if not run or str(run.status).lower() not in {"failed", "blocked"}:
        return ""

    if str(run.status).lower() == "blocked":
        return _last_nonempty_line(run.summary) or "Execução bloqueada; revise a conexão e reexecute."

    payload = _logs_payload(run)
    if isinstance(payload, dict):
        stderr = _last_nonempty_line(payload.get("stderr", ""))
        if stderr:
            return stderr

    summary = _last_nonempty_line(run.summary)
    if summary:
        return summary

    return "Falha registrada sem mensagem detalhada."


def _run_summary(task: Task, run: Run | None) -> dict:
    failed = task.status in {TaskStatus.failed, TaskStatus.blocked}
    return {
        "task_id": task.id,
        "task_status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
        "run_id": run.id if run else None,
        "run_status": run.status if run else None,
        "failure_reason": failure_reason(run) if failed else "",
        "has_log": bool(run),
        "log_url": f"/api/task-runs/{run.id}" if run else None,
    }


@router.get("/task-runs/latest")
def latest_task_runs(
    limit: int = Query(500, ge=1, le=500),
    db: Session = Depends(get_db),
):
    workspace_id = _workspace_id(db)
    tasks = db.scalars(
        select(Task)
        .where(Task.workspace_id == workspace_id)
        .order_by(Task.created_at.desc())
        .limit(limit)
    ).all()
    if not tasks:
        return []

    task_ids = [task.id for task in tasks]
    runs = db.scalars(
        select(Run)
        .where(Run.task_id.in_(task_ids))
        .order_by(Run.started_at.desc(), Run.attempt.desc())
    ).all()
    latest_by_task: dict[str, Run] = {}
    for run in runs:
        latest_by_task.setdefault(run.task_id, run)

    return [_run_summary(task, latest_by_task.get(task.id)) for task in tasks]


@router.get("/task-runs/{run_id}")
def task_run_log(run_id: str, db: Session = Depends(get_db)):
    workspace_id = _workspace_id(db)
    run = db.scalar(
        select(Run)
        .join(Task, Task.id == Run.task_id)
        .where(Run.id == run_id, Task.workspace_id == workspace_id)
    )
    if not run:
        raise HTTPException(404, "Run not found")

    return {
        "id": run.id,
        "task_id": run.task_id,
        "attempt": run.attempt,
        "status": run.status,
        "summary": sanitize_text(run.summary),
        "logs": sanitize_payload(_logs_payload(run)),
        "commit_sha": run.commit_sha,
        "pull_request_url": run.pull_request_url,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
