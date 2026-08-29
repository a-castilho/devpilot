from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditEvent, Project, Run, Task, TaskStatus, Workspace
from app.project_delete_routes import delete_task


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


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


def test_delete_terminal_task_removes_task_and_runs_and_keeps_audit_event():
    db = _session()
    task, run = _task_fixture(db, TaskStatus.failed)
    task_id = task.id
    run_id = run.id

    response = delete_task(task_id, db=db, actor="super-admin@example.com")

    assert response.status_code == 204
    assert db.scalar(select(Task).where(Task.id == task_id)) is None
    assert db.scalar(select(Run).where(Run.id == run_id)) is None
    event = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.task_id == task_id, AuditEvent.action == "task.deleted")
        .order_by(AuditEvent.created_at.desc())
    )
    assert event is not None


def test_delete_active_task_is_rejected_without_removing_it():
    db = _session()
    task, _ = _task_fixture(db, TaskStatus.running)
    task_id = task.id

    with pytest.raises(HTTPException) as error:
        delete_task(task_id, db=db, actor="super-admin@example.com")

    assert error.value.status_code == 409
    assert db.scalar(select(Task).where(Task.id == task_id)) is not None


def test_task_delete_ui_removes_row_and_refreshes_task_data():
    source = Path("app/static/project-delete-ui.js").read_text(encoding="utf-8")

    assert "`/api/tasks/${encodeURIComponent(task.id)}`" in source
    assert "method: 'DELETE'" in source
    assert "detailsRow?.remove();" in source
    assert "row.remove();" in source
    assert "window.loadAllTasks(true)" in source
    assert "MutationObserver" not in source
