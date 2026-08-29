from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, Repository, Workspace
from app.security import require_access, require_super_admin
from app.services.audit import record


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        raise HTTPException(404, "Workspace not found")
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
        raise HTTPException(404, "Project not found")

    project_name = project.name
    project_slug = project.slug
    repository_url = project.repository_url

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
