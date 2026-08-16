import os
from pathlib import Path

os.environ["DEVPILOT_DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("DEVPILOT_BOOTSTRAP_TOKEN", "test-token-with-at-least-32-characters")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditEvent, Workspace
from app.services.audit import record


def test_audit_events_form_hash_chain():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Test", slug="test")
        db.add(workspace)
        db.flush()
        first = record(db, workspace_id=workspace.id, actor="owner", action="one", details={"a": 1})
        db.flush()
        second = record(db, workspace_id=workspace.id, actor="owner", action="two", details={"b": 2})
        db.commit()
        events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
        assert events[0].event_hash == first.event_hash
        assert events[1].previous_hash == events[0].event_hash
        assert second.event_hash != first.event_hash
