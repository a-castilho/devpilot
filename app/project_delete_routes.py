from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select, update
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


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        raise HTTPException(404, "Espaço de trabalho não encontrado")
    return item


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
        raise HTTPException(404, "Projeto não encontrado")

    project_name = project.name
    project_slug = project.slug
    repository_url = project.repository_url

    # Os módulos Jogo/Quest e Investia mantêm chaves estrangeiras próprias.
    # Remova primeiro os registros dependentes para o projeto poder ser
    # excluído tanto no PostgreSQL quanto no SQLite com FKs habilitadas.
    db.execute(delete(QuestMission).where(QuestMission.project_id == project.id))
    investia_config_ids = select(InvestiaProjectConfig.id).where(
        InvestiaProjectConfig.project_id == project.id
    )
    db.execute(
        delete(InvestiaProjectCost).where(
            InvestiaProjectCost.investia_project_id.in_(investia_config_ids)
        )
    )
    db.execute(
        delete(InvestiaDistributionSnapshot).where(
            InvestiaDistributionSnapshot.investia_project_id.in_(investia_config_ids)
        )
    )
    db.execute(
        delete(InvestiaProjectConfig).where(
            InvestiaProjectConfig.project_id == project.id
        )
    )

    # Repositórios sincronizados pertencem à organização GitHub e devem
    # continuar cadastrados. Apenas removemos o vínculo com o projeto.
    db.execute(
        update(Repository)
        .where(Repository.project_id == project.id)
        .values(project_id=None)
    )

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
    # as tarefas e execuções pertencentes ao projeto são removidas junto.
    db.delete(project)
    db.commit()
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
        raise HTTPException(404, "Tarefa não encontrada")

    active_statuses = {
        TaskStatus.queued,
        TaskStatus.planning,
        TaskStatus.running,
        TaskStatus.review,
    }
    if task.status in active_statuses:
        raise HTTPException(409, "Uma tarefa ativa não pode ser excluída")

    task_title = task.title
    task_status = task.status.value if isinstance(task.status, TaskStatus) else str(task.status)
    project_id = task.project_id

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
    return Response(status_code=204)
