from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Task, TaskStatus, Workspace
from app.security import require_access
from app.services.audit import record


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        raise HTTPException(404, "Workspace not found")
    return item


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: str, db: Session = Depends(get_db)):
    """Requeue a terminal task without duplicating its prompt or losing audit history."""

    ws = _workspace(db)
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == ws.id)
    )
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status not in {TaskStatus.blocked, TaskStatus.failed}:
        raise HTTPException(409, "Only blocked or failed tasks can be retried")

    previous_status = task.status.value
    task.status = TaskStatus.queued
    record(
        db,
        workspace_id=ws.id,
        project_id=task.project_id,
        task_id=task.id,
        actor="owner",
        action="task.retry_requested",
        details={"previous_status": previous_status},
    )
    db.commit()
    return {
        "id": task.id,
        "status": task.status,
        "message": "Tarefa recolocada na fila sem perder o histórico anterior.",
    }
