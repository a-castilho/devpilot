from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.investia_models import (
    InvestiaDistributionSnapshot,
    InvestiaProjectConfig,
    InvestiaProjectCost,
)
from app.models import Project, Repository, Task, TaskStatus, Workspace
from app.quest_models import QuestMission
from app.security import require_access, require_super_admin
from app.services.audit import record
from app.services.task_orchestrator import TASK_LEARNING, TASK_RUNTIME


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])

_ACTIVE_RUNTIME_STATES = {"running", "pause_requested", "cancel_requested"}


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        raise HTTPException(404, "Workspace not found")
    return item


def _delete_project_dependents(db: Session, project_id: str) -> None:
    """Remove vínculos com FK que não pertencem ao cascade ORM de Project."""
    db.execute(delete(QuestMission).where(QuestMission.project_id == project_id))

    investia_ids = list(
        db.scalars(
            select(InvestiaProjectConfig.id).where(
                InvestiaProjectConfig.project_id == project_id
            )
        ).all()
    )
    if investia_ids:
        db.execute(
            delete(InvestiaProjectCost).where(
                InvestiaProjectCost.investia_project_id.in_(investia_ids)
            )
        )
        db.execute(
            delete(InvestiaDistributionSnapshot).where(
                InvestiaDistributionSnapshot.investia_project_id.in_(investia_ids)
            )
        )
        db.execute(
            delete(InvestiaProjectConfig).where(
                InvestiaProjectConfig.id.in_(investia_ids)
            )
        )


def _delete_task_dependents(db: Session, task_id: str) -> None:
    """Remove vínculos auxiliares antes da tarefa, inclusive runtime sem FK."""
    db.execute(delete(QuestMission).where(QuestMission.task_id == task_id))
    db.execute(delete(TASK_LEARNING).where(TASK_LEARNING.c.task_id == task_id))
    db.execute(delete(TASK_RUNTIME).where(TASK_RUNTIME.c.task_id == task_id))


def _queued_task_has_active_claim(db: Session, task_id: str) -> bool:
    runtime = db.execute(
        select(
            TASK_RUNTIME.c.state,
            TASK_RUNTIME.c.claim_owner,
        ).where(TASK_RUNTIME.c.task_id == task_id)
    ).mappings().first()
    if runtime is None:
        return False
    return (
        str(runtime["state"] or "") in _ACTIVE_RUNTIME_STATES
        or bool(str(runtime["claim_owner"] or "").strip())
    )


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    project = db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == ws.id,
        )
    )
    if not project:
        raise HTTPException(404, "Project not found")

    project_name = project.name
    project_slug = project.slug
    repository_url = project.repository_url

    try:
        # Repositórios sincronizados pertencem à organização GitHub e devem
        # continuar cadastrados. Apenas removemos o vínculo com o projeto.
        db.execute(
            update(Repository)
            .where(Repository.project_id == project.id)
            .values(project_id=None)
        )

        # Jogo/Quest e Investia possuem FKs próprias para Project/Task e não
        # fazem parte do cascade ORM de Project. Remova-os primeiro para que
        # PostgreSQL e SQLite apliquem a mesma regra de exclusão.
        _delete_project_dependents(db, project.id)

        record(
            db,
            workspace_id=ws.id,
            project_id=project.id,
            actor=actor,
            action="project.deleted",
            details={
                "name": project_name,
                "slug": project_slug,
                "repository": repository_url,
            },
        )

        # Project.tasks usa cascade delete-orphan e Task.runs também, portanto
        # as tarefas e execuções restantes pertencentes ao projeto saem junto.
        db.delete(project)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            "O projeto ainda possui vínculos internos que impedem a exclusão.",
        ) from exc

    return Response(status_code=204)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.workspace_id == ws.id,
        )
    )
    if not task:
        raise HTTPException(404, "Task not found")

    active_statuses = {
        TaskStatus.planning,
        TaskStatus.running,
        TaskStatus.review,
    }
    if task.status in active_statuses:
        raise HTTPException(409, "Active task cannot be deleted")

    task_title = task.title
    task_status = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
    project_id = task.project_id

    try:
        if task.status == TaskStatus.queued:
            if _queued_task_has_active_claim(db, task.id):
                raise HTTPException(409, "Queued task is already claimed and cannot be deleted")

            # Fence atômico contra o worker: somente um lado pode trocar o estado
            # enquanto a tarefa ainda está queued. Se o worker vencer a corrida,
            # a exclusão falha sem tocar em runs, runtime ou auditoria.
            fenced = db.execute(
                update(Task)
                .where(
                    Task.id == task.id,
                    Task.workspace_id == ws.id,
                    Task.status == TaskStatus.queued,
                )
                .values(status=TaskStatus.failed)
            )
            if int(fenced.rowcount or 0) != 1:
                db.rollback()
                raise HTTPException(409, "Queued task changed state and cannot be deleted")

        _delete_task_dependents(db, task.id)

        record(
            db,
            workspace_id=ws.id,
            project_id=project_id,
            task_id=task.id,
            actor=actor,
            action="task.deleted",
            details={
                "title": task_title,
                "status": task_status,
            },
        )

        # Task.runs usa cascade delete-orphan; o evento de auditoria permanece
        # como evidência da ação destrutiva sem manter a tarefa no dashboard.
        db.delete(task)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            "A tarefa ainda possui vínculos internos que impedem a exclusão.",
        ) from exc

    return Response(status_code=204)
