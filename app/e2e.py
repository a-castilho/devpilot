from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Organization,
    Project,
    ProviderCredential,
    Repository,
    Run,
    Task,
    TaskStatus,
    Workspace,
)
from app.security import require_access, require_super_admin
from app.services.audit import record
from app.services.github_delivery import (
    create_github_repository,
    create_or_get_draft_pull_request,
    fetch_commit_ci_status,
    publish_task_branch,
)
from app.services.organizations import project_slug
from app.services.vault import Vault


router = APIRouter(
    prefix="/api/e2e",
    tags=["e2e-delivery"],
    dependencies=[Depends(require_access)],
)


DEFAULT_AGENTS_MD = """# DevPilot delivery rules

- Implement the smallest complete solution that satisfies the task.
- Run relevant tests and a local smoke test before reporting success.
- Keep secrets and credentials out of source code, logs, fixtures and documentation.
- Leave work on the isolated task branch for human review.
- Do not publish remote changes, merge branches or release/deploy without an explicit gated action.
- Include concise technical documentation and a health check in web services.

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**
"""


class ProjectBootstrapRequest(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=150)
    repository_name: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_.-]{2,100}$",
    )
    description: str = Field(default="", max_length=2_000)
    private: bool = True
    queue_initial_task: bool = True
    confirm_remote_creation: bool = False
    agents_md: str = Field(default=DEFAULT_AGENTS_MD, max_length=100_000)
    codex_config: dict[str, Any] = Field(default_factory=dict)


class PublishTaskRequest(BaseModel):
    confirm_reviewed: bool = False


def workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def organization_or_404(db: Session, workspace_id: str, organization_id: str) -> Organization:
    item = db.scalar(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.workspace_id == workspace_id,
            Organization.provider == "github",
        )
    )
    if not item:
        raise HTTPException(404, "GitHub organization not found")
    return item


def organization_access_token(
    db: Session,
    workspace_id: str,
    organization: Organization,
) -> str:
    if not organization.credential_id:
        raise HTTPException(409, "GitHub organization credential is not configured")
    credential = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == organization.credential_id,
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == "github",
            ProviderCredential.enabled.is_(True),
        )
    )
    if not credential:
        raise HTTPException(409, "GitHub organization credential is not available")
    try:
        return Vault().decrypt(credential.encrypted_secret)
    except ValueError as error:
        raise HTTPException(409, "GitHub organization credential cannot be decrypted") from error


def initial_project_prompt(project_name: str) -> str:
    return f"""Create the first complete version of the new project {project_name!r}.

Goal: prove the DevPilot delivery path from an initialized repository to a review-ready implementation.

Build a small Python web application with:
- a GET /health endpoint that returns HTTP 200 and structured JSON;
- a simple root page explaining that the project was created by the DevPilot E2E flow;
- automated tests covering the health endpoint and one functional behavior;
- a README with setup, run, test and architecture instructions;
- a .gitignore suitable for Python;
- a GitHub Actions CI workflow that compiles Python sources and runs the tests;
- no hard-coded secrets or credentials;
- the Compromisso Geral from AGENTS.md included in public project documentation.

Run the tests and a local smoke check. Keep the result on the isolated task branch for review. Do not perform remote publication, merge or release actions; those are separate gated stages.
"""


def _repository_for_project(db: Session, project: Project) -> Repository | None:
    return db.scalar(
        select(Repository).where(
            Repository.project_id == project.id,
            Repository.organization_id == project.organization_id,
        )
    )


def _latest_task(db: Session, project_id: str) -> Task | None:
    return db.scalar(
        select(Task)
        .where(Task.project_id == project_id)
        .order_by(Task.created_at.desc())
        .limit(1)
    )


def _latest_run(db: Session, task_id: str) -> Run | None:
    return db.scalar(
        select(Run)
        .where(Run.task_id == task_id)
        .order_by(Run.started_at.desc())
        .limit(1)
    )


def delivery_status(
    db: Session,
    project: Project,
    access_token: str | None = None,
) -> dict:
    repository = _repository_for_project(db, project)
    task = _latest_task(db, project.id)
    run = _latest_run(db, task.id) if task else None

    ci = {"state": "not_published", "statuses": [], "checks": []}
    if (
        repository
        and run
        and run.commit_sha
        and access_token
    ):
        ci = fetch_commit_ci_status(repository.full_name, access_token, run.commit_sha)

    task_status = task.status.value if task else "not_created"
    execution_status = run.status if run else "not_started"
    review_ready = bool(task and task.status == TaskStatus.review and run and run.status == "success")
    published = bool(run and run.commit_sha and run.pull_request_url)

    if ci.get("state") == "success":
        next_action = "Run homologation validation, then request explicit release approval."
    elif published:
        next_action = "Wait for CI and inspect the draft pull request."
    elif review_ready:
        next_action = "Review locally; when approved, call the gated publish action."
    elif task:
        next_action = "Let the worker execute the implementation task and inspect its run."
    else:
        next_action = "Queue the initial implementation task."

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "slug": project.slug,
            "repository_url": project.repository_url,
            "default_branch": project.default_branch,
        },
        "repository": (
            {
                "id": repository.id,
                "full_name": repository.full_name,
                "visibility": repository.visibility,
            }
            if repository
            else None
        ),
        "task": (
            {
                "id": task.id,
                "title": task.title,
                "status": task_status,
                "branch": task.branch_name,
            }
            if task
            else None
        ),
        "run": (
            {
                "id": run.id,
                "status": execution_status,
                "summary": run.summary,
                "commit_sha": run.commit_sha,
                "pull_request_url": run.pull_request_url,
            }
            if run
            else None
        ),
        "ci": ci,
        "stages": [
            {"name": "remote_repository", "state": "ready" if repository else "missing"},
            {"name": "project_registration", "state": "ready"},
            {"name": "implementation_task", "state": task_status},
            {"name": "local_execution", "state": execution_status},
            {"name": "human_review", "state": "ready" if review_ready else "pending"},
            {"name": "draft_pr", "state": "ready" if published else "gated"},
            {"name": "ci", "state": ci.get("state", "unknown")},
            {"name": "homologation", "state": "manual_gate"},
            {"name": "merge", "state": "blocked_until_validation"},
            {"name": "deploy", "state": "blocked_until_validation"},
        ],
        "next_action": next_action,
    }


@router.post("/projects/bootstrap", status_code=201)
def bootstrap_project(
    payload: ProjectBootstrapRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    if not payload.confirm_remote_creation:
        raise HTTPException(
            409,
            "Remote repository creation requires confirm_remote_creation=true",
        )

    ws = workspace(db)
    organization = organization_or_404(db, ws.id, payload.organization_id)
    access_token = organization_access_token(db, ws.id, organization)

    repository_name = payload.repository_name or project_slug(payload.name)
    slug = project_slug(payload.name)

    existing_project = db.scalar(
        select(Project).where(Project.workspace_id == ws.id, Project.slug == slug)
    )
    if existing_project:
        raise HTTPException(409, f"Project slug already exists: {slug}")

    expected_full_name = f"{organization.external_login}/{repository_name}"
    existing_repository = db.scalar(
        select(Repository).where(
            Repository.organization_id == organization.id,
            Repository.full_name == expected_full_name,
        )
    )
    if existing_repository:
        raise HTTPException(409, f"Repository already registered: {expected_full_name}")

    try:
        remote = create_github_repository(
            organization.external_login,
            access_token,
            repository_name,
            description=payload.description,
            private=payload.private,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(502, str(error)) from error

    project = Project(
        workspace_id=ws.id,
        organization_id=organization.id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        repository_url=remote["clone_url"],
        default_branch=remote["default_branch"],
        agents_md=payload.agents_md,
        codex_config=json.dumps(payload.codex_config),
    )
    db.add(project)
    db.flush()

    repository = Repository(
        organization_id=organization.id,
        project_id=project.id,
        external_id=remote["external_id"],
        name=remote["name"],
        full_name=remote["full_name"],
        description=remote["description"],
        clone_url=remote["clone_url"],
        default_branch=remote["default_branch"],
        visibility=remote["visibility"],
        archived=remote["archived"],
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(repository)
    db.flush()

    task = None
    if payload.queue_initial_task:
        task = Task(
            workspace_id=ws.id,
            project_id=project.id,
            title=f"Criar primeira versão de {project.name}",
            prompt=initial_project_prompt(project.name),
            source="api",
            status=TaskStatus.queued,
            requires_approval=False,
            priority=90,
        )
        db.add(task)
        db.flush()

    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        task_id=task.id if task else None,
        actor=actor,
        action="e2e.project_bootstrapped",
        details={
            "organization_id": organization.id,
            "repository": repository.full_name,
            "visibility": repository.visibility,
            "initial_task": bool(task),
            "release_policy": "merge-and-deploy-blocked-until-validation",
        },
    )
    db.commit()

    return {
        "created": True,
        "project_id": project.id,
        "repository": repository.full_name,
        "task_id": task.id if task else None,
        "status": delivery_status(db, project, access_token=None),
    }


@router.get("/projects/{project_id}/status")
def project_delivery_status(
    project_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_super_admin),
):
    ws = workspace(db)
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == ws.id)
    )
    if not project:
        raise HTTPException(404, "Project not found")

    access_token = None
    if project.organization_id:
        organization = organization_or_404(db, ws.id, project.organization_id)
        access_token = organization_access_token(db, ws.id, organization)

    return delivery_status(db, project, access_token=access_token)


@router.post("/tasks/{task_id}/publish")
def publish_reviewed_task(
    task_id: str,
    payload: PublishTaskRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    if not payload.confirm_reviewed:
        raise HTTPException(409, "Publishing requires confirm_reviewed=true")

    ws = workspace(db)
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == ws.id)
    )
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status != TaskStatus.review:
        raise HTTPException(409, "Task must be in review before publication")

    project = db.scalar(
        select(Project).where(Project.id == task.project_id, Project.workspace_id == ws.id)
    )
    if not project or not project.organization_id:
        raise HTTPException(409, "Task project is not linked to a GitHub organization")

    organization = organization_or_404(db, ws.id, project.organization_id)
    access_token = organization_access_token(db, ws.id, organization)
    repository = _repository_for_project(db, project)
    if not repository:
        raise HTTPException(409, "Project repository linkage is missing")

    run_item = _latest_run(db, task.id)
    if not run_item or run_item.status != "success":
        raise HTTPException(409, "A successful local run is required before publication")

    try:
        publication = publish_task_branch(project, task)
        pull_request = create_or_get_draft_pull_request(
            repository.full_name,
            access_token,
            publication["branch"],
            project.default_branch,
            task.title,
            (
                "DevPilot E2E delivery candidate. Local implementation completed and explicitly "
                "reviewed for remote publication. This PR remains draft. Merge and deploy are "
                "blocked until CI and homologation validation are complete."
            ),
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(502, str(error)) from error

    task.branch_name = publication["branch"]
    run_item.commit_sha = publication["commit_sha"]
    run_item.pull_request_url = pull_request["url"]

    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        task_id=task.id,
        actor=actor,
        action="e2e.task_published_for_review",
        details={
            "branch": task.branch_name,
            "commit_sha": run_item.commit_sha,
            "pull_request_url": run_item.pull_request_url,
            "draft": True,
            "merge": "blocked",
            "deploy": "blocked",
        },
    )
    db.commit()

    ci = fetch_commit_ci_status(repository.full_name, access_token, run_item.commit_sha)
    return {
        "published": True,
        "branch": task.branch_name,
        "commit_sha": run_item.commit_sha,
        "pull_request": pull_request,
        "ci": ci,
        "release_gate": "Merge and deploy remain blocked until explicit validation.",
    }
