from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.db import Base
from app.investia_models import (
    InvestiaCostCategory,
    InvestiaDistributionSnapshot,
    InvestiaProjectConfig,
    InvestiaProjectCost,
)
from app.models import (
    AuditEvent,
    Organization,
    Project,
    Repository,
    Run,
    Task,
    TaskStatus,
    Workspace,
)
from app.project_delete_routes import delete_project, delete_task
from app.quest_models import QuestMission
from app.security import Principal, Role


def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def principal(workspace_id: str) -> Principal:
    return Principal(
        user_id="super-admin-1",
        workspace_id=workspace_id,
        email="super-admin@example.com",
        role=Role.SUPER_ADMIN,
    )


def base_project(db: Session):
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
    return workspace, organization, project


def test_delete_project_removes_all_internal_dependents_and_preserves_repository_record():
    engine = sqlite_engine()

    with Session(engine) as db:
        workspace, organization, project = base_project(db)

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
            status=TaskStatus.completed,
        )
        db.add_all([repository, task])
        db.flush()

        run = Run(task_id=task.id, status="completed")
        mission = QuestMission(
            workspace_id=workspace.id,
            project_id=project.id,
            task_id=task.id,
            title="Missão do jogo",
            description="Validar a entrega real",
        )
        investia = InvestiaProjectConfig(
            workspace_id=workspace.id,
            project_id=project.id,
            external_project_key="projeto-descartavel",
            funding_target=Decimal("1000.00"),
            maximum_funding=Decimal("1000.00"),
        )
        db.add_all([run, mission, investia])
        db.flush()

        cost = InvestiaProjectCost(
            workspace_id=workspace.id,
            investia_project_id=investia.id,
            category=InvestiaCostCategory.development,
            description="Desenvolvimento",
            amount=Decimal("100.00"),
        )
        snapshot = InvestiaDistributionSnapshot(
            workspace_id=workspace.id,
            investia_project_id=investia.id,
            reference_period="2026-09",
            gross_result=Decimal("100.00"),
            approved_costs=Decimal("10.00"),
            net_result=Decimal("90.00"),
            investor_share_percentage=Decimal("10.0000"),
            distributable_pool=Decimal("9.00"),
            total_captured=Decimal("1000.00"),
        )
        db.add_all([cost, snapshot])
        db.commit()

        project_id = project.id
        task_id = task.id
        run_id = run.id
        repository_id = repository.id
        mission_id = mission.id
        investia_id = investia.id
        cost_id = cost.id
        snapshot_id = snapshot.id

        response = delete_project(
            project_id,
            db=db,
            principal=principal(workspace.id),
            actor="user:super-admin",
        )

        assert response.status_code == 204
        assert db.get(Project, project_id) is None
        assert db.get(Task, task_id) is None
        assert db.get(Run, run_id) is None
        assert db.get(QuestMission, mission_id) is None
        assert db.get(InvestiaProjectConfig, investia_id) is None
        assert db.get(InvestiaProjectCost, cost_id) is None
        assert db.get(InvestiaDistributionSnapshot, snapshot_id) is None

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


def test_delete_project_from_another_workspace_is_hidden_and_preserved():
    engine = sqlite_engine()

    with Session(engine) as db:
        own_workspace = Workspace(name="Cliente A", slug="cliente-a")
        other_workspace = Workspace(name="Cliente B", slug="cliente-b")
        db.add_all([own_workspace, other_workspace])
        db.flush()
        other_project = Project(
            workspace_id=other_workspace.id,
            name="Projeto B",
            slug="projeto-b",
            repository_url="https://github.com/example/projeto-b.git",
        )
        db.add(other_project)
        db.commit()
        project_id = other_project.id

        with pytest.raises(HTTPException) as error:
            delete_project(
                project_id,
                db=db,
                principal=principal(own_workspace.id),
                actor="user:super-admin",
            )

        assert error.value.status_code == 404
        assert error.value.detail == "Project not found"
        assert db.get(Project, project_id) is not None

    engine.dispose()


def test_delete_task_removes_quest_mission_before_task():
    engine = sqlite_engine()

    with Session(engine) as db:
        workspace, _organization, project = base_project(db)
        task = Task(
            workspace_id=workspace.id,
            project_id=project.id,
            title="Tarefa concluída",
            prompt="Executar teste",
            status=TaskStatus.completed,
        )
        db.add(task)
        db.flush()

        mission = QuestMission(
            workspace_id=workspace.id,
            project_id=project.id,
            task_id=task.id,
            title="Missão vinculada",
            description="Missão criada pelo jogo",
        )
        db.add(mission)
        db.commit()

        task_id = task.id
        mission_id = mission.id
        response = delete_task(
            task_id,
            db=db,
            principal=principal(workspace.id),
            actor="user:super-admin",
        )

        assert response.status_code == 204
        assert db.get(Task, task_id) is None
        assert db.get(QuestMission, mission_id) is None
        assert db.get(Project, project.id) is not None

    engine.dispose()
