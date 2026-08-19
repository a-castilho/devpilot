from __future__ import annotations

import json

import pytest

from app.agentos.application.errors import CommandExecutionError
from app.agentos.application.platform import (
    AppHubService,
    CouncilService,
    KernelService,
    MemoryOSService,
    ToolHubService,
)
from app.agentos.application.ports import AppRecord, KnowledgeIngestResult
from app.agentos.catalog import AGENT_CATALOG
from app.agentos.domain.platform import memory_namespace


class FakeKnowledge:
    def __init__(self) -> None:
        self.ingests = []
        self.searches = []

    def ingest(self, **kwargs):
        self.ingests.append(kwargs)
        return KnowledgeIngestResult(ids=["chunk-1"], models=["fake-embedding"], providers=["fake"])

    def search(self, **kwargs):
        self.searches.append(kwargs)
        namespace = kwargs["namespace"]
        scores = {
            "memory/task/task-1": 0.70,
            "memory/goal/goal-1": 0.80,
            "memory/project/project-1": 0.95,
            "memory/global": 0.60,
            "default": 0.90,
        }
        return [
            {
                "id": namespace,
                "source": namespace,
                "content": f"context from {namespace}",
                "score": scores.get(namespace, 0.1),
            }
        ]


class FakeEvents:
    def __init__(self) -> None:
        self.items = []

    def publish(self, event) -> None:
        self.items.append(event)


class FakeUow:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeModel:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.responses.pop(0)


class FakeApps:
    def list_apps(self, *, workspace_id: str):
        assert workspace_id == "workspace-1"
        return [
            AppRecord(
                id="project-1",
                name="RegulaAI",
                slug="regulaai",
                description="Regulatory app",
                repository_url="https://example.test/regulaai.git",
                status="active",
            )
        ]


def test_kernel_exposes_six_layer_resource_light_profile():
    status = KernelService().describe()
    assert status["mode"] == "resource-light"
    assert status["resources"]["max_active_agents"] == 1
    assert status["resources"]["parallel_execution"] is False
    assert [layer["name"] for layer in status["layers"]] == [
        "kernel",
        "runtime",
        "memory_os",
        "tool_hub",
        "app_hub",
        "interfaces",
    ]
    assert status["safety"]["council_is_advisory"] is True


def test_toolhub_registers_catalog_capabilities_and_enforces_approval():
    hub = ToolHubService()
    for agent, definition in AGENT_CATALOG.items():
        hub.assert_allowed(
            agent=agent,
            tools=definition.default_tools,
            approval_granted=agent == "devops",
        )

    with pytest.raises(CommandExecutionError):
        hub.assert_allowed(agent="planner", tools=["repo.write"], approval_granted=False)
    with pytest.raises(CommandExecutionError):
        hub.assert_allowed(agent="devops", tools=["deploy.plan"], approval_granted=False)


def test_memory_os_persists_scoped_memory_and_recalls_hierarchy():
    knowledge = FakeKnowledge()
    events = FakeEvents()
    uow = FakeUow()
    memory = MemoryOSService(
        knowledge=knowledge,
        kernel=KernelService(),
        events=events,
        uow=uow,
    )

    result = memory.ingest(
        workspace_id="workspace-1",
        project_id="project-1",
        scope="goal",
        goal_id="goal-1",
        task_id=None,
        source="decision",
        content="Use the hexagonal boundary for model providers.",
        metadata={"kind": "architecture"},
    )
    assert result.chunks == 1
    assert knowledge.ingests[0]["namespace"] == "memory/goal/goal-1"
    assert knowledge.ingests[0]["metadata"]["memory_scope"] == "goal"
    assert uow.commits == 1
    assert events.items[0].name == "agentos.memory.ingested"

    matches = memory.recall(
        workspace_id="workspace-1",
        project_id="project-1",
        goal_id="goal-1",
        task_id="task-1",
        query="architecture boundary",
        top_k=4,
    )
    assert [item["memory_scope"] for item in matches] == [
        "project",
        "goal",
        "task",
        "global",
    ]
    assert [call["namespace"] for call in knowledge.searches] == [
        "memory/task/task-1",
        "memory/goal/goal-1",
        "memory/project/project-1",
        "memory/global",
    ]


def test_memory_namespace_requires_scope_identifier():
    with pytest.raises(ValueError):
        memory_namespace("project")
    with pytest.raises(ValueError):
        memory_namespace("goal")
    with pytest.raises(ValueError):
        memory_namespace("task")


def test_apphub_exposes_projects_as_apps():
    apps = AppHubService(FakeApps()).list_apps(workspace_id="workspace-1")
    assert apps == [
        {
            "id": "project-1",
            "name": "RegulaAI",
            "slug": "regulaai",
            "description": "Regulatory app",
            "repository_url": "https://example.test/regulaai.git",
            "status": "active",
        }
    ]


def test_council_is_sequential_weighted_and_advisory_only():
    knowledge = FakeKnowledge()
    events = FakeEvents()
    uow = FakeUow()
    model = FakeModel(
        [
            {
                "content": json.dumps(
                    {"position": "approve", "confidence": 0.9, "rationale": "Plan is coherent."}
                ),
                "provider": "fake",
                "model": "fake-1",
            },
            {
                "content": json.dumps(
                    {"position": "approve", "confidence": 0.8, "rationale": "Boundaries are sound."}
                ),
                "provider": "fake",
                "model": "fake-1",
            },
            {
                "content": json.dumps(
                    {"position": "reject", "confidence": 0.2, "rationale": "Minor review concern."}
                ),
                "provider": "fake",
                "model": "fake-1",
            },
        ]
    )
    council = CouncilService(
        knowledge=knowledge,
        model=model,
        kernel=KernelService(),
        events=events,
        uow=uow,
    )

    result = council.deliberate(
        workspace_id="workspace-1",
        project_id="project-1",
        namespace="default",
        question="Should this architecture proceed to implementation?",
        members=["planner", "architect", "reviewer"],
        top_k=5,
        consensus_threshold=0.67,
    )

    assert result["decision"] == "approve"
    assert result["advisory_only"] is True
    assert result["consensus"] > 0.8
    assert [vote["agent"] for vote in result["votes"]] == ["planner", "architect", "reviewer"]
    assert len(model.calls) == 3
    assert uow.commits == 1
    assert events.items[-1].name == "agentos.council.deliberated"
