from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditEvent, Project, Task, User, Workspace
from app.services import audit as audit_service


def _user(db: Session, workspace_id: str, email: str, role: str = "OWNER") -> User:
    item = User(
        workspace_id=workspace_id,
        email=email,
        password_hash="test-only",
        role=role,
        active=True,
    )
    db.add(item)
    db.flush()
    return item


def test_account_audit_history_is_scoped_but_chain_stays_global(monkeypatch):
    monkeypatch.setattr(audit_service, "_linux_attestation_enabled", lambda: False)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        user_a = _user(db, workspace.id, "a@example.com")
        user_b = _user(db, workspace.id, "b@example.com")
        super_admin = _user(db, workspace.id, "root@example.com", "SUPER_ADMIN")
        db.commit()
        workspace_id = workspace.id
        user_a_id = user_a.id
        user_b_id = user_b.id
        super_admin_id = super_admin.id

    with Session(engine) as db:
        db.info["principal_user_id"] = user_a_id
        db.info["principal_actor"] = f"user:{user_a_id}"
        first = audit_service.record(
            db,
            workspace_id=workspace_id,
            actor="owner",
            action="account.a",
            details={},
        )
        db.commit()
        first_hash = first.event_hash
        first_id = first.id

    with Session(engine) as db:
        db.info["principal_user_id"] = user_b_id
        db.info["principal_actor"] = f"user:{user_b_id}"
        second = audit_service.record(
            db,
            workspace_id=workspace_id,
            actor="owner",
            action="account.b",
            details={},
        )
        db.commit()
        assert second.previous_hash == first_hash
        second_id = second.id

    with Session(engine) as db:
        db.info["principal_user_id"] = user_a_id
        visible = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
        assert [item.id for item in visible] == [first_id]

    with Session(engine) as db:
        db.info["principal_user_id"] = user_b_id
        visible = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
        assert [item.id for item in visible] == [second_id]

    with Session(engine) as db:
        db.info["principal_user_id"] = super_admin_id
        visible = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
        assert {item.id for item in visible} == {first_id, second_id}

    engine.dispose()


def test_worker_audit_event_inherits_task_owner(monkeypatch):
    monkeypatch.setattr(audit_service, "_linux_attestation_enabled", lambda: False)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        owner = _user(db, workspace.id, "owner@example.com")
        project = Project(
            workspace_id=workspace.id,
            owner_user_id=owner.id,
            name="project",
            slug="project",
            repository_url="https://github.com/example/project.git",
        )
        db.add(project)
        db.flush()
        task = Task(
            workspace_id=workspace.id,
            owner_user_id=owner.id,
            project_id=project.id,
            title="task",
            prompt="task",
        )
        db.add(task)
        db.commit()
        workspace_id = workspace.id
        owner_id = owner.id
        task_id = task.id

    with Session(engine) as db:
        event = audit_service.record(
            db,
            workspace_id=workspace_id,
            task_id=task_id,
            actor="worker",
            action="task.executed",
            details={},
        )
        db.commit()
        assert event.owner_user_id == owner_id

    engine.dispose()
