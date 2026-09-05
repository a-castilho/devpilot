from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import User, Workspace
from app.security import Role
from app.telemetry import (
    SessionCreate,
    TelemetrySession,
    TerminalCommandIn,
    create_session,
    get_session,
    ingest_terminal_command,
    list_sessions,
    now_utc,
)


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


def _recording_session(db: Session, workspace: Workspace, *, seconds: int = 600) -> TelemetrySession:
    started = now_utc()
    item = TelemetrySession(
        workspace_id=workspace.id,
        duration_seconds=seconds,
        status="recording",
        started_at=started,
        ends_at=started + timedelta(seconds=seconds),
        created_at=started,
    )
    db.add(item)
    db.commit()
    return item


def test_create_session_persists_in_authenticated_workspace():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)

    payload = create_session(SessionCreate(duration_seconds=120), db=db)

    stored = db.scalar(select(TelemetrySession).where(TelemetrySession.id == payload["id"]))
    assert stored is not None
    assert stored.workspace_id == customer.id
    assert stored.workspace_id != default.id


def test_list_sessions_does_not_return_foreign_workspace():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)
    foreign = _recording_session(db, default)
    own = _recording_session(db, customer)

    payload = list_sessions(limit=20, db=db)

    assert [item["id"] for item in payload] == [own.id]
    assert foreign.id not in {item["id"] for item in payload}


def test_get_foreign_session_is_hidden():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)
    foreign = _recording_session(db, default)

    with pytest.raises(HTTPException) as error:
        get_session(foreign.id, db=db)

    assert error.value.status_code == 404
    assert error.value.detail == "Telemetry session not found"


def test_terminal_capture_never_writes_into_foreign_active_session():
    db = _session()
    default, customer = _workspaces(db)
    _authenticate(db, customer)
    foreign = _recording_session(db, default)

    result = ingest_terminal_command(
        TerminalCommandIn(command="git status", cwd="/tmp", shell="bash"),
        db=db,
    )

    assert result == {"captured": False, "reason": "no_active_session"}
    db.refresh(foreign)
    assert foreign.status == "recording"
