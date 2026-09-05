from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Project, Run, Task, TaskStatus, Workspace
from app.services import task_orchestrator as orchestrator


@pytest.fixture
def isolated_runtime(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'worker-lease.db'}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    monkeypatch.setattr(orchestrator, "engine", engine)
    monkeypatch.setattr(orchestrator, "SessionLocal", SessionFactory)
    monkeypatch.setattr(orchestrator, "record", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        orchestrator,
        "evaluate_task",
        lambda prompt, needs_approval: SimpleNamespace(requires_approval=False, reasons=[]),
    )
    orchestrator._PROCESS_CLAIMS.clear()
    orchestrator._PROCESS_CLAIM_RENEWED_AT.clear()

    with SessionFactory() as db:
        workspace = Workspace(name="Worker lease", slug="worker-lease")
        db.add(workspace)
        db.flush()
        project = Project(
            workspace_id=workspace.id,
            name="Worker lease project",
            slug="worker-lease-project",
            repository_url="https://example.invalid/repo.git",
        )
        db.add(project)
        db.flush()
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            title="Lease task",
            prompt="Run a safe task",
            status=TaskStatus.queued,
            requires_approval=False,
        )
        db.add(task)
        db.commit()
        task_id = task.id

    try:
        yield engine, SessionFactory, task_id
    finally:
        orchestrator._PROCESS_CLAIMS.clear()
        orchestrator._PROCESS_CLAIM_RENEWED_AT.clear()
        engine.dispose()


def _runtime_row(db: Session, task_id: str):
    return db.execute(
        select(orchestrator.TASK_RUNTIME).where(orchestrator.TASK_RUNTIME.c.task_id == task_id)
    ).mappings().one()


def test_claim_uses_unique_fencing_token_and_heartbeat_extends_lease(isolated_runtime):
    _engine, SessionFactory, task_id = isolated_runtime
    with SessionFactory() as db:
        task = orchestrator.claim_next_task(db, owner="worker:test")
        assert task is not None
        assert task.id == task_id
        claim_owner = str(getattr(task, "_devpilot_claim_owner"))
        assert claim_owner.startswith("worker:test:")
        row = _runtime_row(db, task.id)
        first_lease = orchestrator._aware(row["lease_expires_at"])
        assert row["claim_owner"] == claim_owner
        assert row["state"] == "running"

    orchestrator._PROCESS_CLAIM_RENEWED_AT[task_id] = 0.0
    assert orchestrator.requested_control(task_id) == "running"

    with SessionFactory() as db:
        row = _runtime_row(db, task_id)
        renewed_lease = orchestrator._aware(row["lease_expires_at"])
        assert renewed_lease is not None
        assert first_lease is not None
        assert renewed_lease > first_lease
        assert row["claim_owner"] == claim_owner


def test_stale_worker_detects_replacement_owner_before_control_poll(isolated_runtime):
    _engine, SessionFactory, task_id = isolated_runtime
    with SessionFactory() as db:
        task = orchestrator.claim_next_task(db, owner="worker:old")
        assert task is not None
        old_owner = str(getattr(task, "_devpilot_claim_owner"))
        db.execute(
            update(orchestrator.TASK_RUNTIME)
            .where(orchestrator.TASK_RUNTIME.c.task_id == task_id)
            .values(
                state="running",
                claim_owner="worker:replacement:new-token",
                lease_expires_at=orchestrator.now() + timedelta(seconds=orchestrator.LEASE_SECONDS),
            )
        )
        db.commit()

    assert old_owner != "worker:replacement:new-token"
    with pytest.raises(orchestrator.LostTaskClaim):
        orchestrator.requested_control(task_id)
    assert task_id not in orchestrator._PROCESS_CLAIMS


def test_stale_worker_cannot_finalize_after_claim_was_replaced(isolated_runtime):
    _engine, SessionFactory, task_id = isolated_runtime
    with SessionFactory() as db:
        task = orchestrator.claim_next_task(db, owner="worker:old")
        assert task is not None
        db.execute(
            update(orchestrator.TASK_RUNTIME)
            .where(orchestrator.TASK_RUNTIME.c.task_id == task_id)
            .values(
                state="running",
                claim_owner="worker:new:new-token",
                lease_expires_at=orchestrator.now() + timedelta(seconds=orchestrator.LEASE_SECONDS),
            )
        )
        db.commit()

        run = Run(task_id=task.id, status="success", summary="stale result")
        db.add(run)
        db.flush()
        task.status = TaskStatus.completed

        with pytest.raises(orchestrator.LostTaskClaim):
            orchestrator.mark_worker_finished(db, task, run)
        db.rollback()

    with SessionFactory() as db:
        row = _runtime_row(db, task_id)
        persisted_task = db.get(Task, task_id)
        assert row["state"] == "running"
        assert row["claim_owner"] == "worker:new:new-token"
        assert persisted_task is not None
        assert persisted_task.status == TaskStatus.running


def test_expired_claim_recovery_is_compare_and_set_scoped_to_observed_owner(isolated_runtime, monkeypatch):
    _engine, SessionFactory, task_id = isolated_runtime
    with SessionFactory() as db:
        task = orchestrator.claim_next_task(db, owner="worker:old")
        assert task is not None
        old_owner = str(getattr(task, "_devpilot_claim_owner"))
        db.execute(
            update(orchestrator.TASK_RUNTIME)
            .where(orchestrator.TASK_RUNTIME.c.task_id == task_id)
            .values(lease_expires_at=orchestrator.now() - timedelta(seconds=1))
        )
        db.commit()

    real_execute = Session.execute
    replacement_applied = {"done": False}

    def execute_with_race(self, statement, *args, **kwargs):
        result = real_execute(self, statement, *args, **kwargs)
        sql = str(statement)
        if (
            not replacement_applied["done"]
            and "SELECT task_orchestrator_runtime.task_id" in sql
            and "task_orchestrator_runtime.claim_owner" in sql
        ):
            rows = result.mappings().all()
            replacement_applied["done"] = True
            with SessionFactory() as rival:
                rival.execute(
                    update(orchestrator.TASK_RUNTIME)
                    .where(orchestrator.TASK_RUNTIME.c.task_id == task_id)
                    .values(
                        claim_owner="worker:new:fresh-token",
                        lease_expires_at=orchestrator.now() + timedelta(seconds=orchestrator.LEASE_SECONDS),
                    )
                )
                rival.commit()
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))
        return result

    monkeypatch.setattr(Session, "execute", execute_with_race)
    with SessionFactory() as db:
        orchestrator._recover_expired_claims(db)

    with SessionFactory() as db:
        row = _runtime_row(db, task_id)
        task = db.get(Task, task_id)
        assert replacement_applied["done"] is True
        assert row["state"] == "running"
        assert row["claim_owner"] == "worker:new:fresh-token"
        assert task is not None
        assert task.status == TaskStatus.running
        assert old_owner != row["claim_owner"]
