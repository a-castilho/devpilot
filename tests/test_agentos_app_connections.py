from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agentos.application.app_connections import (
    AppConnectionConflict,
    KnownAppConnectionService,
)
from app.agentos.application.ports import KnowledgeIngestResult
from app.agentos.domain.apps import KNOWN_APP_PROFILES
from app.agentos.infrastructure.platform import SQLAlchemyAppCatalog
from app.agentos.models import AgentAppConnection
from app.db import Base
from app.models import Project, Workspace


class FakeKnowledge:
    def __init__(self) -> None:
        self.ingested = []

    def ingest(self, **kwargs):
        self.ingested.append(kwargs)
        return KnowledgeIngestResult(
            ids=[f"chunk-{len(self.ingested)}"],
            models=["test"],
            providers=["fake"],
        )

    def search(self, **kwargs):
        return []


class Events:
    def __init__(self) -> None:
        self.items = []

    def publish(self, event) -> None:
        self.items.append(event)


class Uow:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


def setup_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    workspace = Workspace(name="DevPilot", slug="default")
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    knowledge = FakeKnowledge()
    events = Events()
    service = KnownAppConnectionService(
        catalog=SQLAlchemyAppCatalog(db),
        knowledge=knowledge,
        events=events,
        uow=Uow(db),
    )
    return db, workspace, service, knowledge, events


def test_connects_three_known_apps_and_seeds_project_memory_once():
    db, workspace, service, knowledge, events = setup_service()
    try:
        first = service.connect(workspace_id=workspace.id)
        assert {item["profile_key"] for item in first} == {
            "regulaai",
            "maquinadeleads",
            "telaviva",
        }
        assert all(item["created_project"] for item in first)
        assert all(item["memory_seeded"] for item in first)
        assert len(knowledge.ingested) == 3
        assert all(item["namespace"].startswith("memory/project/") for item in knowledge.ingested)

        projects = db.scalars(select(Project).where(Project.workspace_id == workspace.id)).all()
        assert len(projects) == 3
        repositories = {project.slug: project.repository_url for project in projects}
        assert repositories["regulaai"] == KNOWN_APP_PROFILES["regulaai"].repository_url
        assert repositories["maquinadeleads"] == KNOWN_APP_PROFILES["maquinadeleads"].repository_url
        assert repositories["telaviva"] == KNOWN_APP_PROFILES["telaviva"].repository_url

        second = service.connect(workspace_id=workspace.id)
        assert not any(item["created_project"] for item in second)
        assert not any(item["memory_seeded"] for item in second)
        assert len(knowledge.ingested) == 3
        assert db.scalar(select(func.count()).select_from(AgentAppConnection)) == 3
        assert len([event for event in events.items if event.name == "agentos.app.connected"]) == 6
    finally:
        db.close()


def test_seed_memory_can_be_deferred_then_completed():
    db, workspace, service, knowledge, _ = setup_service()
    try:
        first = service.connect(
            workspace_id=workspace.id,
            keys=["regulaai"],
            seed_memory=False,
        )
        assert first[0]["memory_version"] == 0
        assert knowledge.ingested == []

        second = service.connect(
            workspace_id=workspace.id,
            keys=["regulaai"],
            seed_memory=True,
        )
        assert second[0]["memory_seeded"] is True
        assert second[0]["memory_version"] == KNOWN_APP_PROFILES["regulaai"].memory_version
        assert len(knowledge.ingested) == 1
    finally:
        db.close()


def test_conflicting_project_slug_is_not_rebound_to_another_repository():
    db, workspace, service, _, _ = setup_service()
    try:
        db.add(
            Project(
                workspace_id=workspace.id,
                name="Other RegulaAI",
                slug="regulaai",
                description="unrelated",
                repository_url="https://github.com/example/other.git",
                default_branch="main",
            )
        )
        db.commit()

        try:
            service.connect(workspace_id=workspace.id, keys=["regulaai"])
        except AppConnectionConflict:
            pass
        else:
            raise AssertionError("known app connection must not hijack an existing slug")

        assert db.scalar(select(func.count()).select_from(AgentAppConnection)) == 0
    finally:
        db.close()


def test_profile_memory_contains_project_specific_guardrails():
    regula = KNOWN_APP_PROFILES["regulaai"].memory_document()
    leads = KNOWN_APP_PROFILES["maquinadeleads"].memory_document()
    telaviva = KNOWN_APP_PROFILES["telaviva"].memory_document()

    assert "nunca inventar deadlines" in regula
    assert "Não criar nova dependência central de n8n" in leads
    assert "autorização em HTTP e WebSocket" in telaviva
