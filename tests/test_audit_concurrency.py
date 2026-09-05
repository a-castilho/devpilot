from __future__ import annotations

import threading

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditEvent, Workspace
from app.services import audit as audit_service


def test_postgresql_workspace_lock_uses_for_update():
    sql = str(
        audit_service._workspace_lock_statement("workspace-1").compile(
            dialect=postgresql.dialect()
        )
    )
    assert "FOR UPDATE" in sql.upper()


def test_sqlite_concurrent_writer_waits_for_prior_audit_transaction(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_service, "_linux_attestation_enabled", lambda: False)
    database_path = tmp_path / "audit-concurrency.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    Base.metadata.create_all(engine)

    with Session(engine) as setup:
        workspace = Workspace(name="Audit concurrency", slug="audit-concurrency")
        setup.add(workspace)
        setup.commit()
        workspace_id = workspace.id

    first_db = Session(engine)
    first = audit_service.record(
        first_db,
        workspace_id=workspace_id,
        actor="worker:first",
        action="concurrent.first",
        details={"order": 1},
    )

    started = threading.Event()
    record_returned = threading.Event()
    finished = threading.Event()
    errors: list[BaseException] = []

    def second_writer() -> None:
        try:
            with Session(engine) as second_db:
                started.set()
                audit_service.record(
                    second_db,
                    workspace_id=workspace_id,
                    actor="worker:second",
                    action="concurrent.second",
                    details={"order": 2},
                )
                record_returned.set()
                second_db.commit()
        except BaseException as error:  # surfaced below in the test thread
            errors.append(error)
        finally:
            finished.set()

    thread = threading.Thread(target=second_writer, daemon=True)
    thread.start()
    assert started.wait(2)

    # The first record already acquired SQLite's transaction write lock through the
    # workspace no-op UPDATE. The second record must not read the same chain head.
    assert not record_returned.wait(0.2)

    first_db.commit()
    first_db.close()

    assert finished.wait(5)
    thread.join(timeout=1)
    assert not errors
    assert record_returned.is_set()

    with Session(engine) as verify_db:
        events = verify_db.scalars(
            select(AuditEvent)
            .where(AuditEvent.workspace_id == workspace_id)
            .order_by(AuditEvent.created_at, AuditEvent.id)
        ).all()
        assert len(events) == 2
        assert events[0].event_hash == first.event_hash
        assert events[1].previous_hash == events[0].event_hash
        verification = audit_service.verify_chain(events)
        assert verification["valid"] is True
        assert verification["events_checked"] == 2
