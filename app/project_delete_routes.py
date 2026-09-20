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
from app.models import Project, Repository, Task, TaskStatus
from app.quest_models import QuestMission
from app.security import Principal, require_access, require_super_admin, session_principal
from app.services.audit import record
from app.services.workspace_scope import workspace_for_principal


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


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
    """QuestMission referencia Task diretamente e precisa sair antes da tarefa."""
    db.execute(delete(QuestMission).where(QuestMission.task_id == task_id))


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_super_admin),
):
    ws = workspace_for_principal(db, principal)
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
    principal: Principal = Depends(session_principal),
    actor: str = Depends(require_super_admin),
):
    ws = workspace_for_principal(db, principal)
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.workspace_id == ws.id,
        )
    )
    if not task:
        raise HTTPException(404, "Task not found")

    active_statuses = {
        TaskStatus.queued,
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
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            "A tarefa ainda possui vínculos internos que impedem a exclusão.",
        ) from exc

    return Response(status_code=204)
