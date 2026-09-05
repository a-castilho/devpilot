from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, Run, Task, TaskStatus, Workspace
from app.project_provisioning_routes import project_config, provision_repository_in_background
from app.security import require_access
from app.services.audit import record
from app.services.failure_recovery import (
    apply_user_guidance,
    ensure_failure_recovery_task,
    find_failure_recovery_task,
    latest_run_for_task,
    resume_original_after_recovery,
)
from app.task_run_routes import failure_details, sanitize_payload


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


class RecoveryGuidance(BaseModel):
    instruction: str = Field(min_length=3, max_length=4000)


def _workspace_id(db: Session) -> str:
    workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == "default"))
    if not workspace_id:
        raise HTTPException(404, "Workspace not found")
    return workspace_id


def _task(db: Session, task_id: str) -> Task:
    workspace_id = _workspace_id(db)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id))
    if not task:
        raise HTTPException(404, "Task not found")
    return task


def _healing_payload(run: Run | None) -> dict:
    if not run or not run.logs:
        return {}
    try:
        payload = json.loads(run.logs)
    except (TypeError, ValueError):
        return {}
    healing = payload.get("self_healing") if isinstance(payload, dict) else None
    return sanitize_payload(healing) if isinstance(healing, dict) else {}


def _status_value(value) -> str:
    return value.value if isinstance(value, TaskStatus) else str(value or "")


def _recovery_state(original: Task, recovery: Task | None) -> str:
    original_status = _status_value(original.status)
    if original_status == TaskStatus.completed.value:
        return "resolved"
    if original_status in {
        TaskStatus.queued.value,
        TaskStatus.planning.value,
        TaskStatus.running.value,
        TaskStatus.review.value,
    }:
        return "retesting"
    if recovery is None:
        return "ready_to_recover"

    recovery_status = _status_value(recovery.status)
    if recovery_status == TaskStatus.awaiting_approval.value:
        return "awaiting_intervention"
    if recovery_status in {
        TaskStatus.queued.value,
        TaskStatus.planning.value,
        TaskStatus.running.value,
        TaskStatus.review.value,
    }:
        return "agent_recovery"
    if recovery_status in {TaskStatus.failed.value, TaskStatus.blocked.value}:
        return "intervention_required"
    if recovery_status == TaskStatus.completed.value and original_status in {
        TaskStatus.failed.value,
        TaskStatus.blocked.value,
    }:
        return "recovery_exhausted"
    return "ready_to_recover"


def _latest_repository_failure(db: Session, original: Task) -> dict | None:
    if not original.project_id:
        return None
    project = db.scalar(
        select(Project).where(
            Project.id == original.project_id,
            Project.workspace_id == original.workspace_id,
        )
    )
    if not project or str(project.repository_url or "").strip():
        return None
    config = project_config(project)
    state = str(config.get("repository_provision_state") or "").strip().lower()
    error = str(config.get("repository_provision_error") or "").strip()
    if state != "failed" or not error:
        return None
    return {
        "category": "repository_not_ready",
        "code": "REPOSITORY_NOT_READY",
        "message": error,
        "requires_authorization": any(
            marker in error.casefold()
            for marker in (
                "credencial",
                "credential",
                "permission",
                "permissão",
                "forbidden",
                "unauthorized",
                "401",
                "403",
            )
        ),
    }


def _payload(db: Session, original: Task) -> dict:
    original_run = latest_run_for_task(db, original.id)
    original_failure = _latest_repository_failure(db, original) or failure_details(original_run)
    recovery = find_failure_recovery_task(db, original)
    recovery_run = latest_run_for_task(db, recovery.id) if recovery else None
    recovery_failure = failure_details(recovery_run) if recovery_run else {
        "category": "",
        "code": "",
        "message": "",
        "requires_authorization": False,
    }
    state = _recovery_state(original, recovery)
    manual = state in {
        "awaiting_intervention",
        "intervention_required",
        "recovery_exhausted",
    }
    can_resume = bool(
        recovery
        and recovery.status == TaskStatus.completed
        and recovery_run
        and recovery_run.status == "success"
        and original.status in {TaskStatus.failed, TaskStatus.blocked}
    )
    return {
        "task_id": original.id,
        "project_id": original.project_id,
        "task_title": original.title,
        "task_status": _status_value(original.status),
        "state": state,
        "manual_intervention_required": manual,
        "can_resume_original": can_resume,
        "failure": original_failure,
        "self_healing": _healing_payload(original_run),
        "original_run": {
            "id": original_run.id if original_run else None,
            "attempt": original_run.attempt if original_run else 0,
            "status": original_run.status if original_run else None,
        },
        "recovery_task": {
            "id": recovery.id,
            "title": recovery.title,
            "status": _status_value(recovery.status),
            "requires_approval": bool(recovery.requires_approval),
            "failure": recovery_failure,
            "run_id": recovery_run.id if recovery_run else None,
            "run_status": recovery_run.status if recovery_run else None,
        } if recovery else None,
    }


def _recover_repository_dependency(db: Session, original: Task, failure: dict) -> bool:
    code = str(failure.get("code") or "").strip().upper()
    if code != "REPOSITORY_NOT_READY" or not original.project_id:
        return False

    project = db.scalar(
        select(Project).where(
            Project.id == original.project_id,
            Project.workspace_id == original.workspace_id,
        )
    )
    if not project:
        return False

    if not str(project.repository_url or "").strip():
        provision_repository_in_background(
            project.id,
            project.workspace_id,
            "owner",
        )
        db.expire_all()
        project = db.scalar(
            select(Project).where(
                Project.id == original.project_id,
                Project.workspace_id == original.workspace_id,
            )
        )

    if not project or not str(project.repository_url or "").strip():
        return False

    original.status = TaskStatus.queued
    original.updated_at = datetime.now(timezone.utc)
    record(
        db,
        workspace_id=original.workspace_id,
        project_id=original.project_id,
        task_id=original.id,
        actor="owner",
        action="failure_recovery.repository_reprovisioned",
        outcome="queued",
        details={
            "repository_url": project.repository_url,
            "failure_code": code,
            "proof_required": True,
        },
    )
    db.flush()
    return True


@router.get("/tasks/{task_id}/recovery")
def recovery_status(task_id: str, db: Session = Depends(get_db)):
    return _payload(db, _task(db, task_id))


@router.post("/tasks/{task_id}/recovery/escalate")
def escalate_recovery(task_id: str, db: Session = Depends(get_db)):
    original = _task(db, task_id)
    if original.status not in {TaskStatus.failed, TaskStatus.blocked}:
        raise HTTPException(409, "Only failed or blocked tasks can enter recovery")
    run = latest_run_for_task(db, original.id)
    failure = _latest_repository_failure(db, original) or failure_details(run)

    if _recover_repository_dependency(db, original, failure):
        db.commit()
        return _payload(db, original)

    recovery = ensure_failure_recovery_task(
        db,
        original_task=original,
        run=run,
        failure=failure,
        actor="owner",
    )
    if not recovery:
        raise HTTPException(409, "Recovery flow is not available for this task")
    db.commit()
    return _payload(db, original)


@router.post("/tasks/{task_id}/recovery/intervene")
def intervene_recovery(
    task_id: str,
    payload: RecoveryGuidance,
    db: Session = Depends(get_db),
):
    original = _task(db, task_id)
    recovery = find_failure_recovery_task(db, original)
    if not recovery:
        run = latest_run_for_task(db, original.id)
        recovery = ensure_failure_recovery_task(
            db,
            original_task=original,
            run=run,
            failure=failure_details(run),
            actor="owner",
        )
        if not recovery:
            raise HTTPException(409, "Recovery flow is not available for this task")
    try:
        apply_user_guidance(
            db,
            original_task=original,
            instruction=payload.instruction,
            actor="owner",
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    db.commit()
    return _payload(db, original)


@router.post("/tasks/{task_id}/recovery/resume")
def resume_original(task_id: str, db: Session = Depends(get_db)):
    original = _task(db, task_id)
    recovery = find_failure_recovery_task(db, original)
    if not recovery:
        raise HTTPException(409, "Recovery task not found")
    recovery_run = latest_run_for_task(db, recovery.id)
    if recovery.status != TaskStatus.completed or not recovery_run or recovery_run.status != "success":
        raise HTTPException(409, "Recovery must complete successfully before retesting the original task")
    resumed = resume_original_after_recovery(
        db,
        recovery_task=recovery,
        recovery_run=recovery_run,
    )
    if not resumed:
        raise HTTPException(409, "Original task cannot be resumed")
    db.commit()
    return _payload(db, original)
