from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Organization, Project, ProviderCredential, Run, Task, Workspace
from app.security import require_access
from app.services.github_workflows import fetch_deployment_evidence, fetch_workflow_evidence
from app.services.vault import Vault


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


def _workspace_id(db: Session) -> str:
    workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == "default"))
    if not workspace_id:
        raise HTTPException(404, "Workspace not found")
    return workspace_id


def _github_access_token(db: Session, project: Project) -> str | None:
    if not project.organization_id:
        return None
    organization = db.scalar(
        select(Organization).where(Organization.id == project.organization_id)
    )
    if not organization or not organization.credential_id:
        return None
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == organization.credential_id,
            ProviderCredential.provider == "github",
            ProviderCredential.enabled.is_(True),
        )
    )
    if not credential:
        return None
    return Vault().decrypt(credential.encrypted_secret)


def _task_context(task_id: str, db: Session) -> tuple[Task, Project, Run | None]:
    workspace_id = _workspace_id(db)
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
    )
    if not task:
        raise HTTPException(404, "Task not found")
    project = db.scalar(
        select(Project).where(Project.id == task.project_id, Project.workspace_id == workspace_id)
    )
    if not project:
        raise HTTPException(404, "Project not found")
    run = db.scalar(
        select(Run)
        .where(Run.task_id == task.id)
        .order_by(Run.started_at.desc(), Run.attempt.desc())
        .limit(1)
    )
    return task, project, run


@router.get("/tasks/{task_id}/workflow-evidence")
def task_workflow_evidence(task_id: str, db: Session = Depends(get_db)):
    task, project, run = _task_context(task_id, db)
    if not run or not str(run.commit_sha or "").strip():
        return {
            "task_id": task.id,
            "run_id": run.id if run else None,
            "correlated": False,
            "reason": "missing_persisted_commit",
            "workflow": None,
            "jobs": [],
        }

    try:
        evidence = fetch_workflow_evidence(
            project.repository_url,
            run.commit_sha,
            _github_access_token(db, project),
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(502, str(error)) from error

    return {
        "task_id": task.id,
        "run_id": run.id,
        "pull_request_url": run.pull_request_url or None,
        **evidence,
    }


@router.get("/tasks/{task_id}/deployment-evidence")
def task_deployment_evidence(task_id: str, db: Session = Depends(get_db)):
    task, project, run = _task_context(task_id, db)
    if not run or not str(run.commit_sha or "").strip():
        return {
            "task_id": task.id,
            "run_id": run.id if run else None,
            "correlated": False,
            "reason": "missing_persisted_commit",
            "deployment": None,
        }

    try:
        evidence = fetch_deployment_evidence(
            project.repository_url,
            run.commit_sha,
            _github_access_token(db, project),
        )
    except (RuntimeError, ValueError) as error:
        raise HTTPException(502, str(error)) from error

    return {
        "task_id": task.id,
        "run_id": run.id,
        **evidence,
    }
