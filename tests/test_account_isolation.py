from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Project, Run, Task, User, Workspace
from app.services.schema import ensure_runtime_schema


def _user(db: Session, workspace_id: str, *, email: str, role: str) -> User:
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


def _project(
    db: Session,
    workspace_id: str,
    owner_user_id: str | None,
    *,
    slug: str,
) -> Project:
    item = Project(
        workspace_id=workspace_id,
        owner_user_id=owner_user_id,
        name=slug,
        slug=slug,
        repository_url=f"https://github.com/example/{slug}.git",
    )
    db.add(item)
    db.flush()
    return item


def _task(
    db: Session,
    workspace_id: str,
    project_id: str,
    owner_user_id: str | None,
    *,
    title: str,
) -> Task:
    item = Task(
        workspace_id=workspace_id,
        owner_user_id=owner_user_id,
        project_id=project_id,
        title=title,
        prompt=title,
    )
    db.add(item)
    db.flush()
    return item


def test_regular_user_sees_only_owned_projects_tasks_and_runs():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        user_a = _user(db, workspace.id, email="a@example.com", role="OWNER")
        user_b = _user(db, workspace.id, email="b@example.com", role="OWNER")
        project_a = _project(db, workspace.id, user_a.id, slug="project-a")
        project_b = _project(db, workspace.id, user_b.id, slug="project-b")
        task_a = _task(db, workspace.id, project_a.id, user_a.id, title="task-a")
        task_b = _task(db, workspace.id, project_b.id, user_b.id, title="task-b")
        run_a = Run(task_id=task_a.id, status="completed")
        run_b = Run(task_id=task_b.id, status="completed")
        db.add_all([run_a, run_b])
        db.commit()
        user_a_id = user_a.id
        project_a_id = project_a.id
        project_b_id = project_b.id
        task_a_id = task_a.id
        run_a_id = run_a.id
        run_b_id = run_b.id

    with Session(engine) as db:
        db.info["principal_user_id"] = user_a_id

        assert [item.id for item in db.scalars(select(Project)).all()] == [project_a_id]
        assert [item.id for item in db.scalars(select(Task)).all()] == [task_a_id]
        assert db.get(Project, project_b_id) is None

        visible_run = db.scalar(
            select(Run)
            .join(Task, Task.id == Run.task_id)
            .where(Run.id == run_a_id)
        )
        hidden_run = db.scalar(
            select(Run)
            .join(Task, Task.id == Run.task_id)
            .where(Run.id == run_b_id)
        )
        assert visible_run is not None
        assert hidden_run is None

    engine.dispose()


def test_super_admin_sees_every_users_projects_and_tasks():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        super_admin = _user(db, workspace.id, email="root@example.com", role="SUPER_ADMIN")
        user_a = _user(db, workspace.id, email="a@example.com", role="OWNER")
        user_b = _user(db, workspace.id, email="b@example.com", role="OWNER")
        project_a = _project(db, workspace.id, user_a.id, slug="project-a")
        project_b = _project(db, workspace.id, user_b.id, slug="project-b")
        _task(db, workspace.id, project_a.id, user_a.id, title="task-a")
        _task(db, workspace.id, project_b.id, user_b.id, title="task-b")
        db.commit()
        super_admin_id = super_admin.id

    with Session(engine) as db:
        db.info["principal_user_id"] = super_admin_id
        assert len(db.scalars(select(Project)).all()) == 2
        assert len(db.scalars(select(Task)).all()) == 2

    engine.dispose()


def test_new_project_and_task_are_bound_to_authenticated_account_automatically():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        user = _user(db, workspace.id, email="owner@example.com", role="OWNER")
        db.commit()
        workspace_id = workspace.id
        user_id = user.id

    with Session(engine) as db:
        db.info["principal_user_id"] = user_id
        project = Project(
            workspace_id=workspace_id,
            name="automatic-owner",
            slug="automatic-owner",
            repository_url="https://github.com/example/automatic-owner.git",
        )
        db.add(project)
        db.flush()
        assert project.owner_user_id == user_id

        task = Task(
            workspace_id=workspace_id,
            project_id=project.id,
            title="owned task",
            prompt="owned task",
        )
        db.add(task)
        db.flush()
        assert task.owner_user_id == user_id
        db.rollback()

    engine.dispose()


def test_background_task_inherits_project_owner_without_authenticated_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()
        user = _user(db, workspace.id, email="owner@example.com", role="OWNER")
        project = _project(db, workspace.id, user.id, slug="project-a")
        db.commit()
        workspace_id = workspace.id
        user_id = user.id
        project_id = project.id

    with Session(engine) as db:
        task = Task(
            workspace_id=workspace_id,
            project_id=project_id,
            title="worker-created",
            prompt="worker-created",
        )
        db.add(task)
        db.flush()
        assert task.owner_user_id == user_id
        db.rollback()

    engine.dispose()


def test_runtime_schema_assigns_legacy_rows_to_workspace_super_admin():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id VARCHAR(36) PRIMARY KEY, workspace_id VARCHAR(36), email VARCHAR(320), "
                "password_hash VARCHAR(255), role VARCHAR(20), active BOOLEAN, created_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE projects ("
                "id VARCHAR(36) PRIMARY KEY, workspace_id VARCHAR(36), organization_id VARCHAR(36), "
                "name VARCHAR(150), slug VARCHAR(100), repository_url VARCHAR(500))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE tasks ("
                "id VARCHAR(36) PRIMARY KEY, workspace_id VARCHAR(36), project_id VARCHAR(36), "
                "title VARCHAR(240), prompt TEXT, status VARCHAR(30))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, workspace_id, email, password_hash, role, active, created_at) "
                "VALUES ('root', 'ws', 'root@example.com', 'x', 'admin', 1, '2026-01-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO projects (id, workspace_id, organization_id, name, slug, repository_url) "
                "VALUES ('project', 'ws', NULL, 'Legacy', 'legacy', '')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tasks (id, workspace_id, project_id, title, prompt, status) "
                "VALUES ('task', 'ws', 'project', 'Legacy task', 'Legacy task', 'queued')"
            )
        )

    ensure_runtime_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("projects")}
    task_columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
    assert "owner_user_id" in columns
    assert "owner_user_id" in task_columns

    with engine.connect() as connection:
        assert connection.execute(text("SELECT role FROM users WHERE id = 'root'")).scalar_one() == "SUPER_ADMIN"
        assert connection.execute(text("SELECT owner_user_id FROM projects WHERE id = 'project'")).scalar_one() == "root"
        assert connection.execute(text("SELECT owner_user_id FROM tasks WHERE id = 'task'")).scalar_one() == "root"

    engine.dispose()
