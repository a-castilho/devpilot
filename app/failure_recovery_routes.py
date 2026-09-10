from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Organization, Project, ProviderCredential, Run, Task, TaskStatus, Workspace
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


def _run_history(db: Session, task: Task | None) -> list[Run]:
    if not task:
        return []
    return list(
        db.scalars(
            select(Run)
            .where(Run.task_id == task.id)
            .order_by(Run.started_at.desc(), Run.id.desc())
        ).all()
    )


def _run_snapshot(run: Run | None) -> dict:
    if not run:
        return {
            "id": None,
            "attempt": 0,
            "status": None,
            "summary": "",
            "started_at": None,
            "finished_at": None,
        }
    return {
        "id": run.id,
        "attempt": run.attempt,
        "status": run.status,
        "summary": str(run.summary or "")[:1200],
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


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


def _github_access_restored(db: Session, original: Task) -> bool:
    project = db.scalar(
        select(Project).where(
            Project.id == original.project_id,
            Project.workspace_id == original.workspace_id,
        )
    )
    if not project or not project.organization_id:
        return False
    organization = db.scalar(
        select(Organization).where(
            Organization.id == project.organization_id,
            Organization.workspace_id == original.workspace_id,
            Organization.provider == "github",
        )
    )
    if not organization or not organization.credential_id:
        return False
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == organization.credential_id,
            ProviderCredential.workspace_id == original.workspace_id,
            ProviderCredential.provider == "github",
            ProviderCredential.enabled.is_(True),
        )
    )
    return credential is not None


def _reconcile_external_blocker(db: Session, original: Task) -> bool:
    recovery = find_failure_recovery_task(db, original)
    if not recovery or recovery.status not in {
        TaskStatus.awaiting_approval,
        TaskStatus.failed,
        TaskStatus.blocked,
    }:
        return False

    recovery_run = latest_run_for_task(db, recovery.id)
    recovery_failure = failure_details(recovery_run) if recovery_run else {}
    category = str(recovery_failure.get("category") or "").strip().lower()
    code = str(recovery_failure.get("code") or "").strip().upper()
    prompt = str(recovery.prompt or "")
    github_blocker = (
        category == "github_auth"
        or code == "GITHUB_ACCESS_DENIED"
        or "[failure-category:github_auth]" in prompt.lower()
        or "[failure-code:GITHUB_ACCESS_DENIED]" in prompt
    )
    if not github_blocker or not _github_access_restored(db, original):
        return False

    now = datetime.now(timezone.utc)
    previous_status = _status_value(recovery.status)
    recovery.status = TaskStatus.queued
    recovery.requires_approval = False
    recovery.approved_at = recovery.approved_at or now
    recovery.updated_at = now
    recovery.prompt = (
        f"{prompt.rstrip()}\n\n"
        f"[failure-external-blocker-resolved:{now.isoformat()}]\n"
        "DEPENDÊNCIA EXTERNA REVALIDADA AUTOMATICAMENTE\n"
        "A credencial GitHub vinculada ao projeto está presente e ativa no estado atual. "
        "A missão de recuperação foi reenfileirada para validar o acesso real e continuar sem exigir nova intervenção humana."
    )[:100_000]
    record(
        db,
        workspace_id=original.workspace_id,
        project_id=original.project_id,
        task_id=recovery.id,
        actor="system",
        action="failure_recovery.external_blocker_resolved",
        outcome="queued",
        details={
            "original_task_id": original.id,
            "blocker": "github_auth",
            "previous_status": previous_status,
        },
    )
    db.commit()
    return True


def _payload(db: Session, original: Task) -> dict:
    original_run = latest_run_for_task(db, original.id)
    original_failure = failure_details(original_run)
    recovery = find_failure_recovery_task(db, original)
    recovery_runs = _run_history(db, recovery)
    recovery_run = recovery_runs[0] if recovery_runs else None
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
    blocker = ""
    if state == "intervention_required" and recovery_run:
        blocker = str(recovery_run.summary or recovery_failure.get("message") or "")[:1200]

    return {
        "task_id": original.id,
        "task_title": original.title,
        "task_status": _status_value(original.status),
        "state": state,
        "manual_intervention_required": manual,
        "can_resume_original": can_resume,
        "blocker": blocker,
        "failure": original_failure,
        "self_healing": _healing_payload(original_run),
        "original_run": _run_snapshot(original_run),
        "recovery_task": {
            "id": recovery.id,
            "title": recovery.title,
            "status": _status_value(recovery.status),
            "requires_approval": bool(recovery.requires_approval),
            "failure": recovery_failure,
            "run_id": recovery_run.id if recovery_run else None,
            "run_status": recovery_run.status if recovery_run else None,
            "execution_count": len(recovery_runs),
            "latest_execution": _run_snapshot(recovery_run),
            "next_execution_number": len(recovery_runs) + 1,
        } if recovery else None,
    }


@router.get("/tasks/{task_id}/recovery")
def recovery_status(task_id: str, db: Session = Depends(get_db)):
    original = _task(db, task_id)
    _reconcile_external_blocker(db, original)
    return _payload(db, original)


@router.post("/tasks/{task_id}/recovery/escalate")
def escalate_recovery(task_id: str, db: Session = Depends(get_db)):
    original = _task(db, task_id)
    if _reconcile_external_blocker(db, original):
        return _payload(db, original)
    if original.status not in {TaskStatus.failed, TaskStatus.blocked}:
        raise HTTPException(409, "Only failed or blocked tasks can enter recovery")
    run = latest_run_for_task(db, original.id)
    failure = failure_details(run)
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
    before_count = len(_run_history(db, recovery))
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
    result = _payload(db, original)
    result["resume_request"] = {
        "accepted": True,
        "recovery_task_id": recovery.id,
        "previous_execution_count": before_count,
        "expected_next_execution": before_count + 1,
        "status": _status_value(recovery.status),
        "message": "Orientação registrada. A missão de recuperação foi reenfileirada para uma nova execução.",
    }
    return result


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
