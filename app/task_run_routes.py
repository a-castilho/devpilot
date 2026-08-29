from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Run, Task, TaskStatus, Workspace
from app.security import Principal, Role, require_access, require_roles
from app.services.audit import record


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])

_SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\"']+"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)

_FAILURE_CODES = {
    "github_auth": "GITHUB_ACCESS_DENIED",
    "codex_auth": "CODEX_AUTH_REQUIRED",
    "git_network": "GIT_NETWORK_ERROR",
    "filesystem_permission": "FILESYSTEM_PERMISSION_DENIED",
    "database": "DATABASE_UNAVAILABLE",
    "repository_state": "REPOSITORY_STATE_INVALID",
    "unknown": "EXECUTION_FAILED",
}

_GITHUB_AUTH_PATTERNS = (
    "requested url returned error: 401",
    "requested url returned error: 403",
    "authentication failed",
    "could not read username",
    "repository access denied",
    "write access to repository not granted",
    "repository not found",
    "permission denied (publickey)",
)
_CODEX_AUTH_PATTERNS = (
    "not logged in",
    "invalid api key",
    "codex login",
    "401 unauthorized",
)
_GIT_NETWORK_PATTERNS = (
    "could not resolve host",
    "failed to connect",
    "connection timed out",
    "connection reset",
    "network is unreachable",
    "temporary failure in name resolution",
)
_FILESYSTEM_PATTERNS = (
    "operation not permitted",
    "read-only file system",
    "permission denied",
)
_DATABASE_PATTERNS = (
    "sqlalchemy.exc.operationalerror",
    "database is unavailable",
    "could not connect to server",
)
_REPOSITORY_STATE_PATTERNS = (
    "already exists and is not an empty directory",
    "not a git repository",
    "index.lock",
    "shallow.lock",
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


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    normalized = str(text or "").casefold()
    return any(pattern in normalized for pattern in patterns)


def classify_failure_text(value: str) -> str:
    text = str(value or "")
    if _matches(text, _GITHUB_AUTH_PATTERNS):
        return "github_auth"
    if _matches(text, _GIT_NETWORK_PATTERNS):
        return "git_network"
    if _matches(text, _REPOSITORY_STATE_PATTERNS):
        return "repository_state"
    if _matches(text, _CODEX_AUTH_PATTERNS):
        return "codex_auth"
    if _matches(text, _DATABASE_PATTERNS):
        return "database"
    if _matches(text, _FILESYSTEM_PATTERNS):
        return "filesystem_permission"
    return "unknown"


def _friendly_failure_message(category: str, fallback: str = "") -> str:
    messages = {
        "github_auth": (
            "Credencial GitHub sem acesso ao repositório. Revalide a integração da organização "
            "e permita leitura do repositório antes de executar novamente."
        ),
        "codex_auth": (
            "O Codex não está autenticado no ambiente de execução. Autorize o Codex no worker "
            "antes de executar novamente."
        ),
        "git_network": (
            "Falha de rede ao acessar o repositório. O DevPilot pode tentar novamente sem alterar o projeto."
        ),
        "repository_state": (
            "O checkout local do repositório está inconsistente e precisa ser reparado antes da execução."
        ),
        "filesystem_permission": (
            "O sistema operacional bloqueou o acesso necessário. Revise as permissões do ambiente de execução."
        ),
        "database": (
            "O banco de dados do DevPilot está indisponível. A execução foi interrompida para evitar inconsistências."
        ),
    }
    return messages.get(category) or fallback or "Falha registrada sem mensagem detalhada."


def failure_details(run: Run | None) -> dict:
    if not run or str(run.status).lower() != "failed":
        return {
            "category": "",
            "code": "",
            "message": "",
            "requires_authorization": False,
        }

    payload = _logs_payload(run)
    if isinstance(payload, dict):
        healing = payload.get("self_healing")
        if isinstance(healing, dict):
            category = str(healing.get("category") or "unknown")
            message = _last_nonempty_line(healing.get("message", ""))
            if message:
                return {
                    "category": category,
                    "code": _FAILURE_CODES.get(category, _FAILURE_CODES["unknown"]),
                    "message": message,
                    "requires_authorization": bool(healing.get("requires_authorization", False)),
                }

        raw_error = str(payload.get("stderr") or payload.get("raw") or "")
        category = classify_failure_text(raw_error)
        raw_message = _last_nonempty_line(raw_error)
        if category != "unknown":
            return {
                "category": category,
                "code": _FAILURE_CODES[category],
                "message": _friendly_failure_message(category, raw_message),
                "requires_authorization": category in {
                    "github_auth",
                    "codex_auth",
                    "filesystem_permission",
                },
            }
        if raw_message:
            return {
                "category": "unknown",
                "code": _FAILURE_CODES["unknown"],
                "message": raw_message,
                "requires_authorization": False,
            }

    summary = _last_nonempty_line(run.summary)
    category = classify_failure_text(summary)
    if category != "unknown":
        return {
            "category": category,
            "code": _FAILURE_CODES[category],
            "message": _friendly_failure_message(category, summary),
            "requires_authorization": category in {
                "github_auth",
                "codex_auth",
                "filesystem_permission",
            },
        }
    if summary:
        return {
            "category": "unknown",
            "code": _FAILURE_CODES["unknown"],
            "message": summary,
            "requires_authorization": False,
        }

    return {
        "category": "unknown",
        "code": _FAILURE_CODES["unknown"],
        "message": "Falha registrada sem mensagem detalhada.",
        "requires_authorization": False,
    }


def failure_reason(run: Run | None) -> str:
    return str(failure_details(run).get("message") or "")


def _run_summary(task: Task, run: Run | None) -> dict:
    needs_attention = task.status in {TaskStatus.failed, TaskStatus.blocked}
    details = failure_details(run) if needs_attention else {
        "category": "",
        "code": "",
        "message": "",
        "requires_authorization": False,
    }
    return {
        "task_id": task.id,
        "task_status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
        "run_id": run.id if run else None,
        "run_status": run.status if run else None,
        "failure_reason": details["message"],
        "failure_category": details["category"],
        "failure_code": details["code"],
        "requires_authorization": details["requires_authorization"],
        "has_log": bool(run),
        "log_url": f"/api/task-runs/{run.id}" if run else None,
    }


@router.delete("/tasks/queued")
def delete_queued_tasks(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_roles(Role.SUPER_ADMIN)),
):
    """Remove queued tasks that have never started, preserving an audit record.

    A queued task with an existing run may represent a retry and is intentionally
    retained so execution evidence is never destroyed by this cleanup operation.
    """
    workspace_id = _workspace_id(db)
    queued = db.scalars(
        select(Task)
        .where(
            Task.workspace_id == workspace_id,
            Task.owner_user_id == principal.user_id,
            Task.status == TaskStatus.queued,
            ~Task.runs.any(),
        )
        .order_by(Task.created_at.asc())
    ).all()

    for task in queued:
        record(
            db,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor=principal.actor,
            action="task.queued_deleted",
            details={
                "title": task.title,
                "source": task.source,
                "priority": task.priority,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "reason": "super_admin_queue_cleanup",
            },
        )
        db.delete(task)

    db.commit()
    return {"deleted": len(queued), "status": "ok"}


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


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: str, db: Session = Depends(get_db)):
    workspace_id = _workspace_id(db)
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
    )
    if not task:
        raise HTTPException(404, "Task not found")

    previous_status = task.status
    if previous_status not in {TaskStatus.failed, TaskStatus.blocked}:
        raise HTTPException(409, "Only failed or blocked tasks can be retried")

    latest_run = db.scalar(
        select(Run)
        .where(Run.task_id == task.id)
        .order_by(Run.started_at.desc(), Run.attempt.desc())
        .limit(1)
    )
    details = failure_details(latest_run)
    task.status = TaskStatus.queued
    record(
        db,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        task_id=task.id,
        actor="owner",
        action="task.retried",
        outcome="queued",
        details={
            "previous_status": (
                previous_status.value
                if isinstance(previous_status, TaskStatus)
                else str(previous_status)
            ),
            "failure_category": details.get("category", ""),
            "reused_task": True,
        },
    )
    db.commit()
    return {
        "task_id": task.id,
        "status": "queued",
        "reused_task": True,
        "failure_category": details.get("category", ""),
    }


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
        "failure": failure_details(run),
        "commit_sha": run.commit_sha,
        "pull_request_url": run.pull_request_url,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }
