from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditEvent, Organization, Project, Repository, Run, Task, Workspace
from app.project_delete_routes import delete_project


def test_delete_project_removes_tasks_and_runs_but_preserves_repository_link_record():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        workspace = Workspace(name="DevPilot", slug="default")
        db.add(workspace)
        db.flush()

        organization = Organization(
            workspace_id=workspace.id,
            provider="github",
            name="A Castilho",
            slug="a-castilho",
            external_login="a-castilho",
        )
        db.add(organization)
        db.flush()

        project = Project(
            workspace_id=workspace.id,
            organization_id=organization.id,
            name="Projeto descartável",
            slug="projeto-descartavel",
            repository_url="https://github.com/a-castilho/projeto-descartavel.git",
            default_branch="main",
        )
        db.add(project)
        db.flush()

        repository = Repository(
            organization_id=organization.id,
            project_id=project.id,
            external_id="repo-1",
            name="projeto-descartavel",
            full_name="a-castilho/projeto-descartavel",
            clone_url=project.repository_url,
        )
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            title="Tarefa do projeto",
            prompt="Executar teste",
        )
        db.add_all([repository, task])
        db.flush()

        run = Run(task_id=task.id, status="started")
        db.add(run)
        db.commit()

        project_id = project.id
        task_id = task.id
        run_id = run.id
        repository_id = repository.id

        response = delete_project(project_id, db=db, actor="user:super-admin")

        assert response.status_code == 204
        assert db.get(Project, project_id) is None
        assert db.get(Task, task_id) is None
        assert db.get(Run, run_id) is None

        kept_repository = db.get(Repository, repository_id)
        assert kept_repository is not None
        assert kept_repository.project_id is None

        audit = db.scalar(
            select(AuditEvent).where(
                AuditEvent.workspace_id == workspace.id,
                AuditEvent.action == "project.deleted",
            )
        )
        assert audit is not None
        assert audit.project_id == project_id
        assert audit.actor == "user:super-admin"

    engine.dispose()
