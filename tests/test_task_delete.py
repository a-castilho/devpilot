from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditEvent, Project, Run, Task, TaskStatus, Workspace
from app.project_delete_routes import delete_task
from app.services.task_orchestrator import TASK_LEARNING, TASK_RUNTIME


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


def _runtime(db: Session, task_id: str, *, state: str, owner: str = "") -> None:
    db.execute(
        insert(TASK_RUNTIME).values(
            task_id=task_id,
            state=state,
            version=1,
            auto_advance=False,
            claim_owner=owner,
            lease_expires_at=None,
            last_action="test",
            last_message="",
            archived_at=None,
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


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
    assert event.details


def test_delete_unclaimed_queued_task_is_fenced_then_removed_with_runtime_cleanup():
    db = _session()
    task, run = _task_fixture(db, TaskStatus.queued)
    task_id = task.id
    run_id = run.id
    _runtime(db, task_id, state="queued")
    db.execute(
        insert(TASK_LEARNING).values(
            task_id=task_id,
            step="queued",
            happened="fila antiga",
            rationale="teste",
            concept="fencing",
            observe="registro",
            learned="seguro",
            evidence="{}",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    response = delete_task(task_id, db=db, actor="super-admin@example.com")

    assert response.status_code == 204
    assert db.scalar(select(Task).where(Task.id == task_id)) is None
    assert db.scalar(select(Run).where(Run.id == run_id)) is None
    assert db.execute(select(TASK_RUNTIME.c.task_id).where(TASK_RUNTIME.c.task_id == task_id)).scalar_one_or_none() is None
    assert db.execute(select(TASK_LEARNING.c.task_id).where(TASK_LEARNING.c.task_id == task_id)).scalar_one_or_none() is None
    event = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.task_id == task_id, AuditEvent.action == "task.deleted")
        .order_by(AuditEvent.created_at.desc())
    )
    assert event is not None
    assert '"status": "queued"' in event.details


def test_delete_queued_task_with_active_worker_claim_is_rejected():
    db = _session()
    task, _ = _task_fixture(db, TaskStatus.queued)
    task_id = task.id
    _runtime(db, task_id, state="running", owner="worker:test")

    with pytest.raises(HTTPException) as error:
        delete_task(task_id, db=db, actor="super-admin@example.com")

    assert error.value.status_code == 409
    assert error.value.detail == "Queued task is already claimed and cannot be deleted"
    assert db.scalar(select(Task).where(Task.id == task_id)) is not None
    assert db.execute(select(TASK_RUNTIME.c.task_id).where(TASK_RUNTIME.c.task_id == task_id)).scalar_one_or_none() == task_id


@pytest.mark.parametrize(
    "task_status",
    [
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
        delete_task(task_id, db=db, actor="super-admin@example.com")

    assert error.value.status_code == 409
    assert error.value.detail == "Active task cannot be deleted"
    assert db.scalar(select(Task).where(Task.id == task_id)) is not None


def test_delete_missing_task_returns_404():
    db = _session()
    workspace = Workspace(name="DevPilot", slug="default")
    db.add(workspace)
    db.commit()

    with pytest.raises(HTTPException) as error:
        delete_task("missing-task", db=db, actor="super-admin@example.com")

    assert error.value.status_code == 404
    assert error.value.detail == "Task not found"


def test_task_delete_ui_contract_includes_refresh_and_no_global_observer():
    source = Path("app/static/project-delete-ui.js").read_text(encoding="utf-8")

    assert "`/api/tasks/${encodeURIComponent(task.id)}`" in source
    assert "method: 'DELETE'" in source
    assert "detailsRow?.remove();" in source
    assert "row.remove();" in source
    assert "window.loadAllTasks(true)" in source
    assert "MutationObserver" not in source


def test_task_action_cards_offer_super_admin_delete_for_queued_and_terminal_tasks():
    source = Path("app/static/task-completion-documentation.js").read_text(encoding="utf-8")

    assert "const DELETABLE_TASK_STATUSES" in source
    assert "'queued'" in source
    assert "button.className = 'link delete-task'" in source
    assert "button.dataset.taskDelete" in source
    assert "isSuperAdmin()" in source
    assert "await api(`/tasks/${encodeURIComponent(taskId)}`, {method: 'DELETE'})" in source
    assert "Esta ação não pode ser desfeita" in source
