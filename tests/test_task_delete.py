from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditEvent, Project, Run, Task, TaskStatus, Workspace
from app.project_delete_routes import delete_task
from app.security import Principal, Role


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _principal(workspace_id: str) -> Principal:
    return Principal(
        user_id="super-admin-1",
        workspace_id=workspace_id,
        email="super-admin@example.com",
        role=Role.SUPER_ADMIN,
    )


def _task_fixture(db: Session, status: TaskStatus) -> tuple[Task, Run]:
    workspace = Workspace(name="DevPilot", slug="default")
    db.add(workspace)
    db.flush()
    project = Project(
        workspace_id=workspace.id,
        name="Delete task test",
        slug="delete-task-test",
        repository_url="https://github.com/example/delete-task-test.git",
    )
    db.add(project)
    db.flush()
    task = Task(
        workspace_id=workspace.id,
        project_id=project.id,
        title="Tarefa removível",
        prompt="teste",
        status=status,
    )
    db.add(task)
    db.flush()
    run = Run(task_id=task.id, status="failed")
    db.add(run)
    db.commit()
    return task, run


@pytest.mark.parametrize(
    "task_status",
    [
        TaskStatus.awaiting_approval,
        TaskStatus.completed,
        TaskStatus.failed,
        TaskStatus.blocked,
    ],
)
def test_delete_terminal_task_removes_task_and_runs_and_keeps_audit_event(task_status):
    db = _session()
    task, run = _task_fixture(db, task_status)
    task_id = task.id
    run_id = run.id

    response = delete_task(
        task_id,
        db=db,
        principal=_principal(task.workspace_id),
        actor="super-admin@example.com",
    )

    assert response.status_code == 204
    assert db.scalar(select(Task).where(Task.id == task_id)) is None
    assert db.scalar(select(Run).where(Run.id == run_id)) is None
    event = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.task_id == task_id, AuditEvent.action == "task.deleted")
        .order_by(AuditEvent.created_at.desc())
    )
    assert event is not None
    assert event.workspace_id == task.workspace_id
    assert event.details


@pytest.mark.parametrize(
    "task_status",
    [
        TaskStatus.queued,
        TaskStatus.planning,
        TaskStatus.running,
        TaskStatus.review,
    ],
)
def test_delete_active_task_is_rejected_without_removing_it(task_status):
    db = _session()
    task, _ = _task_fixture(db, task_status)
    task_id = task.id

    with pytest.raises(HTTPException) as error:
        delete_task(
            task_id,
            db=db,
            principal=_principal(task.workspace_id),
            actor="super-admin@example.com",
        )

    assert error.value.status_code == 409
    assert error.value.detail == "Active task cannot be deleted"
    assert db.scalar(select(Task).where(Task.id == task_id)) is not None


def test_delete_missing_task_returns_404():
    db = _session()
    workspace = Workspace(name="DevPilot", slug="default")
    db.add(workspace)
    db.commit()

    with pytest.raises(HTTPException) as error:
        delete_task(
            "missing-task",
            db=db,
            principal=_principal(workspace.id),
            actor="super-admin@example.com",
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Task not found"


def test_delete_task_from_another_workspace_is_hidden_and_preserved():
    db = _session()
    own_workspace = Workspace(name="Cliente A", slug="cliente-a")
    other_workspace = Workspace(name="Cliente B", slug="cliente-b")
    db.add_all([own_workspace, other_workspace])
    db.flush()
    other_project = Project(
        workspace_id=other_workspace.id,
        name="Projeto B",
        slug="projeto-b",
        repository_url="https://github.com/example/projeto-b.git",
    )
    db.add(other_project)
    db.flush()
    other_task = Task(
        workspace_id=other_workspace.id,
        project_id=other_project.id,
        title="Tarefa B",
        prompt="teste",
        status=TaskStatus.completed,
    )
    db.add(other_task)
    db.commit()

    with pytest.raises(HTTPException) as error:
        delete_task(
            other_task.id,
            db=db,
            principal=_principal(own_workspace.id),
            actor="super-admin@example.com",
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Task not found"
    assert db.scalar(select(Task).where(Task.id == other_task.id)) is not None


def test_task_delete_ui_contract_includes_refresh_and_no_global_observer():
    source = Path("app/static/project-delete-ui.js").read_text(encoding="utf-8")

    assert "`/api/tasks/${encodeURIComponent(task.id)}`" in source
    assert "method: 'DELETE'" in source
    assert "detailsRow?.remove();" in source
    assert "row.remove();" in source
    assert "window.loadAllTasks(true)" in source
    assert "MutationObserver" not in source
