import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import failure_recovery_routes as recovery_routes
from app import task_run_routes
from app.db import Base
from app.models import Project, Run, Task, TaskStatus, User, Workspace
from app.security import Role


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _workspaces(db: Session) -> tuple[Workspace, Workspace]:
    default = Workspace(name="DevPilot", slug="default")
    customer = Workspace(name="Cliente B", slug="cliente-b")
    db.add_all([default, customer])
    db.commit()
    return default, customer


def _authenticate(db: Session, workspace: Workspace) -> User:
    user = User(
        workspace_id=workspace.id,
        email=f"owner-{workspace.slug}@example.com",
        password_hash="not-used",
        role=Role.OWNER.value,
        active=True,
    )
    db.add(user)
    db.commit()
    db.info["principal_user_id"] = user.id
    return user


def _task(db: Session, workspace: Workspace, *, slug: str, status: TaskStatus) -> tuple[Project, Task, Run]:
    project = Project(
        workspace_id=workspace.id,
        name=f"Projeto {slug}",
        slug=f"project-{slug}",
        repository_url=f"https://github.com/example/{slug}.git",
    )
    db.add(project)
    db.flush()
    task = Task(
        workspace_id=workspace.id,
        project_id=project.id,
        title=f"Task {slug}",
        prompt="teste",
        status=status,
    )
    db.add(task)
    db.flush()
    run = Run(
        task_id=task.id,
        attempt=1,
        status="failed" if status in {TaskStatus.failed, TaskStatus.blocked} else "success",
        summary=f"run {slug}",
        logs="{}",
    )
    db.add(run)
    db.commit()
    return project, task, run


def test_latest_task_runs_only_lists_authenticated_workspace():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)
    _, foreign_task, _ = _task(db, default, slug="foreign", status=TaskStatus.completed)
    _, own_task, _ = _task(db, customer, slug="own", status=TaskStatus.completed)

    payload = task_run_routes.latest_task_runs(limit=500, db=db)

    assert [item["task_id"] for item in payload] == [own_task.id]
    assert foreign_task.id not in {item["task_id"] for item in payload}


def test_retry_foreign_task_is_hidden_and_not_mutated():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)
    _, foreign_task, _ = _task(db, default, slug="retry-foreign", status=TaskStatus.failed)

    with pytest.raises(HTTPException) as error:
        task_run_routes.retry_task(foreign_task.id, db=db)

    assert error.value.status_code == 404
    db.refresh(foreign_task)
    assert foreign_task.status == TaskStatus.failed


def test_foreign_run_log_is_hidden():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)
    _, _, foreign_run = _task(db, default, slug="run-foreign", status=TaskStatus.failed)

    with pytest.raises(HTTPException) as error:
        task_run_routes.task_run_log(foreign_run.id, db=db)

    assert error.value.status_code == 404
    assert error.value.detail == "Run not found"


def test_failure_recovery_foreign_task_is_hidden_before_recovery_logic():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)
    _, foreign_task, _ = _task(db, default, slug="recovery-foreign", status=TaskStatus.failed)

    with pytest.raises(HTTPException) as error:
        recovery_routes.recovery_status(foreign_task.id, db=db)

    assert error.value.status_code == 404
    assert error.value.detail == "Task not found"
