from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.agentos.application.errors import CommandExecutionError
from app.agentos.application.extensions import (
    ExtensionActivationRecord,
    ExtensionMarketplaceService,
)
from app.agentos.application.intelligence import RepositoryIntelligenceService
from app.agentos.application.platform import ToolHubService
from app.agentos.domain.intelligence import (
    DependencyEdge,
    DependencyGraph,
    RepositoryDocument,
    RepositoryIndexRecord,
    RepositorySnapshot,
)


class FakeKnowledge:
    def __init__(self):
        self.ingested = []

    def ingest(self, **kwargs):
        self.ingested.append(kwargs)

        @dataclass
        class Result:
            ids: list[str]
            models: list[str]
            providers: list[str]

            @property
            def chunks(self):
                return len(self.ids)

        return Result(ids=[str(len(self.ingested))], models=["fake"], providers=["test"])

    def search(self, **kwargs):
        return [{"source": kwargs["namespace"], "content": kwargs["query"], "score": 1.0}]


class FakeSnapshots:
    def snapshot(self, *, project_id: str, refresh: bool = False):
        return RepositorySnapshot(
            project_id=project_id,
            snapshot_hash="a" * 64,
            documents=(
                RepositoryDocument(
                    path="app/main.py",
                    language="python",
                    kind="code",
                    content="from app.service import run\n",
                    content_hash="b" * 64,
                ),
                RepositoryDocument(
                    path="app/service.py",
                    language="python",
                    kind="code",
                    content="def run(): return 1\n",
                    content_hash="c" * 64,
                ),
            ),
        )

    def graph(self, snapshot):
        return DependencyGraph(
            nodes=("app/main.py", "app/service.py"),
            edges=(DependencyEdge("app/main.py", "app/service.py"),),
        )


class FakeIndexes:
    def __init__(self):
        self.record = None

    def get(self, *, workspace_id: str, project_id: str):
        return self.record

    def save(self, **kwargs):
        self.record = RepositoryIndexRecord(**kwargs)
        return self.record


class FakeEvents:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


class FakeUow:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeActivations:
    def __init__(self):
        self.records = []

    def list(self, *, workspace_id: str, project_id: str | None = None):
        return [
            item for item in self.records
            if project_id is None or item.project_id == project_id
        ]

    def set_enabled(self, *, workspace_id: str, project_id: str, extension_key: str,
                    extension_version: int, enabled: bool):
        self.records = [
            item for item in self.records
            if not (item.project_id == project_id and item.extension_key == extension_key)
        ]
        record = ExtensionActivationRecord(
            project_id=project_id,
            extension_key=extension_key,
            extension_version=extension_version,
            enabled=enabled,
        )
        self.records.append(record)
        return record


def test_repository_intelligence_is_idempotent_and_reports_impact():
    knowledge = FakeKnowledge()
    indexes = FakeIndexes()
    events = FakeEvents()
    uow = FakeUow()
    service = RepositoryIntelligenceService(
        snapshots=FakeSnapshots(),
        indexes=indexes,
        knowledge=knowledge,
        events=events,
        uow=uow,
    )

    first = service.index_project(workspace_id="ws", project_id="p1")
    second = service.index_project(workspace_id="ws", project_id="p1")
    impact = service.impact(project_id="p1", path="app/service.py", depth=2)

    assert first["indexed"] is True
    assert second["indexed"] is False
    assert len(knowledge.ingested) == 3  # two files plus manifest, no duplicate second index
    assert impact.impacted_files == ("app/main.py",)
    assert events.events[-1].name == "agentos.repository.indexed"


def test_marketplace_activation_scopes_toolhub_capabilities():
    activations = FakeActivations()
    events = FakeEvents()
    uow = FakeUow()
    marketplace = ExtensionMarketplaceService(
        activations=activations,
        events=events,
        uow=uow,
    )
    tools = ToolHubService(activations)

    marketplace.set_enabled(
        workspace_id="ws",
        project_id="p1",
        extension_key="assurance",
        enabled=True,
    )

    tools.assert_allowed(
        agent="security",
        tools=["repo.read", "code.impact"],
        approval_granted=False,
        workspace_id="ws",
        project_id="p1",
    )

    with pytest.raises(CommandExecutionError):
        tools.assert_allowed(
            agent="frontend",
            tools=["repo.read"],
            approval_granted=False,
            workspace_id="ws",
            project_id="p1",
        )


def test_toolhub_keeps_delivery_approval_gate_with_extensions():
    activations = FakeActivations()
    marketplace = ExtensionMarketplaceService(
        activations=activations,
        events=FakeEvents(),
        uow=FakeUow(),
    )
    tools = ToolHubService(activations)
    marketplace.set_enabled(
        workspace_id="ws",
        project_id="p1",
        extension_key="operations",
        enabled=True,
    )

    with pytest.raises(CommandExecutionError):
        tools.assert_allowed(
            agent="devops",
            tools=["deploy.plan"],
            approval_granted=False,
            workspace_id="ws",
            project_id="p1",
        )

    tools.assert_allowed(
        agent="devops",
        tools=["deploy.plan"],
        approval_granted=True,
        workspace_id="ws",
        project_id="p1",
    )
