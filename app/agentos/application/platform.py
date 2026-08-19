from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from app.agentos.application.errors import CommandExecutionError, ModelUnavailable
from app.agentos.application.ports import (
    AppCatalogPort,
    EventBusPort,
    ExecutionRepositoryPort,
    KnowledgeIngestResult,
    KnowledgePort,
    LanguageModelPort,
    UnitOfWorkPort,
)
from app.agentos.catalog import AGENT_CATALOG
from app.agentos.domain.events import DomainEvent
from app.agentos.domain.platform import (
    PLATFORM_LAYERS,
    TOOL_REGISTRY,
    MemoryScope,
    ResourceBudget,
    memory_namespace,
)


class KernelService:
    def __init__(self, budget: ResourceBudget | None = None) -> None:
        self.budget = budget or ResourceBudget()

    def describe(self) -> dict[str, Any]:
        return {
            "mode": self.budget.mode,
            "layers": [asdict(layer) for layer in PLATFORM_LAYERS],
            "resources": asdict(self.budget),
            "safety": {
                "human_approval_for_delivery": True,
                "automatic_push_merge_deploy": False,
                "council_is_advisory": True,
            },
        }

    def validate_council_members(self, members: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(member.strip().lower() for member in members if member.strip()))
        if not normalized:
            raise ValueError("Council requires at least one member")
        if len(normalized) > self.budget.max_council_members:
            raise ValueError(
                f"Council exceeds resource-light limit of {self.budget.max_council_members} members"
            )
        unknown = [member for member in normalized if member not in AGENT_CATALOG]
        if unknown:
            raise ValueError(f"Unknown council agents: {', '.join(unknown)}")
        return normalized


class ToolHubService:
    def list_tools(self, *, agent: str | None = None) -> list[dict[str, Any]]:
        items = []
        for spec in TOOL_REGISTRY.values():
            if agent and agent not in spec.allowed_agents:
                continue
            items.append(asdict(spec))
        return items

    def assert_allowed(
        self,
        *,
        agent: str,
        tools: list[str],
        approval_granted: bool,
    ) -> None:
        for tool in tools:
            spec = TOOL_REGISTRY.get(tool)
            if not spec:
                raise CommandExecutionError(f"Tool is not registered: {tool}")
            if agent not in spec.allowed_agents:
                raise CommandExecutionError(f"Agent {agent} is not authorized for tool {tool}")
            if spec.approval_required and not approval_granted:
                raise CommandExecutionError(f"Tool {tool} requires explicit human approval")


class RuntimeService:
    def __init__(
        self,
        *,
        executions: ExecutionRepositoryPort,
        kernel: KernelService,
    ) -> None:
        self.executions = executions
        self.kernel = kernel

    def status(self) -> dict[str, Any]:
        active = self.executions.next_active()
        return {
            "mode": self.kernel.budget.mode,
            "max_active_agents": self.kernel.budget.max_active_agents,
            "parallel_execution": self.kernel.budget.parallel_execution,
            "active_execution": None
            if active is None
            else {
                "id": active.id,
                "goal_id": active.goal_id,
                "project_id": active.project_id,
                "status": active.status,
                "current_step_id": active.current_step_id,
            },
        }


class MemoryOSService:
    def __init__(self, *, knowledge: KnowledgePort, kernel: KernelService) -> None:
        self.knowledge = knowledge
        self.kernel = kernel

    def ingest(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        scope: MemoryScope,
        goal_id: str | None,
        task_id: str | None,
        source: str,
        content: str,
        metadata: dict[str, Any],
    ) -> KnowledgeIngestResult:
        namespace = memory_namespace(
            scope,
            project_id=project_id,
            goal_id=goal_id,
            task_id=task_id,
        )
        enriched = dict(metadata)
        enriched.update({"memory_scope": scope, "goal_id": goal_id, "task_id": task_id})
        return self.knowledge.ingest(
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            source=source,
            content=content,
            metadata=enriched,
        )

    def recall(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        goal_id: str | None,
        task_id: str | None,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        limit = min(top_k, self.kernel.budget.max_rag_matches)
        namespaces: list[tuple[str, str]] = []
        if task_id:
            namespaces.append(("task", memory_namespace("task", task_id=task_id)))
        if goal_id:
            namespaces.append(("goal", memory_namespace("goal", goal_id=goal_id)))
        if project_id:
            namespaces.append(("project", memory_namespace("project", project_id=project_id)))
        namespaces.append(("global", memory_namespace("global")))

        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for scope, namespace in namespaces:
            matches = self.knowledge.search(
                workspace_id=workspace_id,
                project_id=project_id if scope != "global" else None,
                namespace=namespace,
                query=query,
                top_k=limit,
            )
            for match in matches:
                identity = str(match.get("id") or f"{match.get('source')}:{match.get('content')}")
                if identity in seen:
                    continue
                seen.add(identity)
                item = dict(match)
                item["memory_scope"] = scope
                merged.append(item)
        merged.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        return merged[:limit]


class AppHubService:
    def __init__(self, apps: AppCatalogPort) -> None:
        self.apps = apps

    def list_apps(self, *, workspace_id: str) -> list[dict[str, Any]]:
        return [asdict(app) for app in self.apps.list_apps(workspace_id=workspace_id)]


class CouncilService:
    def __init__(
        self,
        *,
        knowledge: KnowledgePort,
        model: LanguageModelPort,
        kernel: KernelService,
        events: EventBusPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self.knowledge = knowledge
        self.model = model
        self.kernel = kernel
        self.events = events
        self.uow = uow

    @staticmethod
    def _parse_vote(content: str) -> dict[str, Any]:
        text = content.strip()
        start = text.find("{")
        end = text.rfind("}")
        data: dict[str, Any] = {}
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                data = {}
        position = str(data.get("position", "abstain")).lower()
        if position not in {"approve", "reject", "abstain"}:
            position = "abstain"
        try:
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        rationale = str(data.get("rationale") or text)[:4_000]
        return {"position": position, "confidence": confidence, "rationale": rationale}

    def deliberate(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        question: str,
        members: list[str],
        top_k: int,
        consensus_threshold: float,
    ) -> dict[str, Any]:
        members = self.kernel.validate_council_members(members)
        matches = self.knowledge.search(
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            query=question,
            top_k=min(top_k, self.kernel.budget.max_rag_matches),
        )
        context = "\n\n".join(
            f"[{index + 1}] {item.get('source', 'context')}: {item.get('content', '')}"
            for index, item in enumerate(matches)
        )[: self.kernel.budget.max_context_chars]

        votes: list[dict[str, Any]] = []
        for member in members:
            definition = AGENT_CATALOG[member]
            try:
                response = self.model.chat(
                    [
                        {
                            "role": "system",
                            "content": (
                                f"You are the {member} member of an advisory engineering council. "
                                f"Role: {definition.description} Return JSON only with keys "
                                "position (approve|reject|abstain), confidence (0..1), rationale. "
                                "Do not claim to grant human approval for deployment, merge or production actions."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Question:\n{question}\n\nContext:\n{context or '(none)'}",
                        },
                    ]
                )
                vote = self._parse_vote(str(response.get("content", "")))
                vote.update(
                    {
                        "agent": member,
                        "provider": response.get("provider", ""),
                        "model": response.get("model", ""),
                    }
                )
            except ModelUnavailable:
                vote = {
                    "agent": member,
                    "position": "abstain",
                    "confidence": 0.0,
                    "rationale": "Model unavailable for this council member.",
                    "provider": "",
                    "model": "",
                }
            votes.append(vote)

        approve = sum(v["confidence"] for v in votes if v["position"] == "approve")
        reject = sum(v["confidence"] for v in votes if v["position"] == "reject")
        total = sum(v["confidence"] for v in votes)
        winning = max(approve, reject)
        consensus = winning / total if total else 0.0
        if total and approve > reject and consensus >= consensus_threshold:
            decision = "approve"
        elif total and reject > approve and consensus >= consensus_threshold:
            decision = "reject"
        else:
            decision = "human_review"

        result = {
            "decision": decision,
            "consensus": round(consensus, 4),
            "threshold": consensus_threshold,
            "advisory_only": True,
            "members": members,
            "votes": votes,
            "rag_matches": len(matches),
        }
        self.events.publish(
            DomainEvent(
                name="agentos.council.deliberated",
                workspace_id=workspace_id,
                project_id=project_id,
                payload={
                    "decision": decision,
                    "consensus": result["consensus"],
                    "members": members,
                    "rag_matches": len(matches),
                    "advisory_only": True,
                },
            )
        )
        self.uow.commit()
        return result
