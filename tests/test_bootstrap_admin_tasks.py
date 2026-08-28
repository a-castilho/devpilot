from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Project, Run, Task, User, Workspace
from app.services.bootstrap_admin_tasks import (
    RADAR_PR_URL,
    RADAR_TASK_TITLE,
    bootstrap_regulaai_radar_admin_task,
)


def test_bootstrap_regulaai_radar_task_is_idempotent_and_owned_by_super_admin():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="Default", slug="default")
        db.add(workspace)
        db.flush()

        admin = User(
            workspace_id=workspace.id,
            email="admin@example.com",
            password_hash="test",
            role="SUPER_ADMIN",
            active=True,
        )
        db.add(admin)
        db.flush()

        project = Project(
            workspace_id=workspace.id,
            owner_user_id=admin.id,
            name="Regula AI",
            slug="regulaai",
            description="Inteligência regulatória",
            repository_url="https://github.com/a-castilho/regulaai",
            default_branch="main",
        )
        db.add(project)
        db.commit()
        admin_id = admin.id
        project_id = project.id

    assert bootstrap_regulaai_radar_admin_task(engine) is True
    assert bootstrap_regulaai_radar_admin_task(engine) is False

    with Session(engine) as db:
        tasks = db.scalars(select(Task).where(Task.title == RADAR_TASK_TITLE)).all()
        assert len(tasks) == 1
        task = tasks[0]
        assert task.owner_user_id == admin_id
        assert task.project_id == project_id
        assert task.status.value == "completed"
        assert task.requires_approval is False

        runs = db.scalars(select(Run).where(Run.task_id == task.id)).all()
        assert len(runs) == 1
        assert runs[0].pull_request_url == RADAR_PR_URL

        assert db.scalar(select(func.count(Task.id))) == 1
        assert db.scalar(select(func.count(Run.id))) == 1


def test_bootstrap_is_noop_without_regulaai_project():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    assert bootstrap_regulaai_radar_admin_task(engine) is False
