from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Run, Task, TaskStatus, Workspace
from app.security import require_access
from app.services.audit import record

router = APIRouter(prefix="/api/game", dependencies=[Depends(require_access)])

_GAME_STATE = {
    TaskStatus.queued: "MISSION_READY",
    TaskStatus.running: "IN_OPERATION",
    TaskStatus.blocked: "SHIELD_BLOCKED",
    TaskStatus.failed: "SHOT_FAILED",
    TaskStatus.completed: "MISSION_COMPLETE",
}


def _workspace_id(db: Session) -> str:
    workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == "default"))
    if not workspace_id:
        raise HTTPException(404, "Workspace not found")
    return workspace_id


def _latest_run(db: Session, task_id: str) -> Run | None:
    return db.scalar(
        select(Run)
        .where(Run.task_id == task_id)
        .order_by(Run.started_at.desc(), Run.attempt.desc())
        .limit(1)
    )


def _technical_phase(run: Run | None) -> str:
    if not run or not run.logs:
        return "waiting"
    text = str(run.logs).lower()
    if "analysis-read-only" in text or '"mode": "analysis' in text:
        return "scan"
    if '"mode": "execute"' in text:
        return "fire"
    if "budget-blocked" in text:
        return "shield"
    if run.status == "success":
        return "hit"
    if run.status == "failed":
        return "miss"
    return "running"


def _payload(task: Task, run: Run | None) -> dict:
    status = task.status if isinstance(task.status, TaskStatus) else TaskStatus(str(task.status))
    phase = _technical_phase(run)
    game_state = _GAME_STATE.get(status, "MISSION_READY")
    if status == TaskStatus.running:
        game_state = {
            "scan": "SCANNING",
            "fire": "FIRING",
            "shield": "SHIELD_BLOCKED",
            "hit": "TARGET_HIT",
            "miss": "SHOT_FAILED",
        }.get(phase, "IN_OPERATION")
    return {
        "task_id": task.id,
        "project_id": task.project_id,
        "technical_status": status.value,
        "game_state": game_state,
        "technical_phase": phase,
        "run": None if not run else {
            "id": run.id,
            "attempt": run.attempt,
            "status": run.status,
            "summary": run.summary,
            "commit_sha": run.commit_sha,
            "pull_request_url": run.pull_request_url,
        },
    }


@router.get("/missions/{task_id}")
def mission_state(task_id: str, db: Session = Depends(get_db)):
    workspace_id = _workspace_id(db)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id))
    if not task:
        raise HTTPException(404, "Task not found")
    return _payload(task, _latest_run(db, task.id))


@router.post("/missions/{task_id}/fire")
def fire_mission(task_id: str, db: Session = Depends(get_db)):
    workspace_id = _workspace_id(db)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id))
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status not in {TaskStatus.queued, TaskStatus.failed, TaskStatus.blocked}:
        raise HTTPException(409, "Mission cannot be fired from its current state")
    previous = task.status
    task.status = TaskStatus.queued
    record(
        db,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        task_id=task.id,
        actor="game-ui",
        action="game.weapon.fire",
        outcome="queued",
        details={"previous_status": previous.value if isinstance(previous, TaskStatus) else str(previous)},
    )
    db.commit()
    return _payload(task, _latest_run(db, task.id))
