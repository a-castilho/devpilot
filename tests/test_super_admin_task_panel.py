from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.frontend_ui_routes import create_super_admin_task, super_admin_task_summaries
from app.models import Base, Project, User, Workspace
from app.schemas import TaskCreate
from app.security import Principal, Role


def build_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def seed(db):
    ws = Workspace(name="DevPilot", slug="default")
    db.add(ws)
    db.flush()
    admin = User(
        workspace_id=ws.id,
        email="admin@example.test",
        password_hash="x",
        role="SUPER_ADMIN",
        active=True,
    )
    other = User(
        workspace_id=ws.id,
        email="other@example.test",
        password_hash="x",
        role="SUPER_ADMIN",
        active=True,
    )
    db.add_all([admin, other])
    db.flush()
    project = Project(
        workspace_id=ws.id,
        owner_user_id=admin.id,
        name="Regula AI",
        slug="regula-ai",
        description="",
        repository_url="https://github.com/a-castilho/regulaai",
        default_branch="main",
        agents_md="",
        codex_config="{}",
    )
    db.add(project)
    db.commit()
    return ws, admin, other, project


def principal(user):
    return Principal(
        user_id=user.id,
        workspace_id=user.workspace_id,
        email=user.email,
        role=Role.SUPER_ADMIN,
    )


def test_created_task_is_owned_and_visible_to_same_super_admin_only():
    db = build_db()
    _, admin, other, project = seed(db)
    payload = TaskCreate(
        project_id=project.id,
        title="Radar Regula AI editorial automático",
        prompt="Implementar e validar o Radar editorial no Regula AI.",
        source="api",
        priority=90,
        requires_approval=False,
    )

    created = create_super_admin_task(payload=payload, db=db, principal=principal(admin))

    assert created["project_name"] == "Regula AI"
    mine = super_admin_task_summaries(limit=20, db=db, principal=principal(admin))
    mine_by_id = {item["id"]: item for item in mine}
    assert created["id"] in mine_by_id
    assert mine_by_id[created["id"]]["title"] == "Radar Regula AI editorial automático"

    others = super_admin_task_summaries(limit=20, db=db, principal=principal(other))
    assert others == []
