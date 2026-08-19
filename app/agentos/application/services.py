from __future__ import annotations

from typing import Any

from app.agentos.application.errors import ModelUnavailable
from app.agentos.application.ports import (
    EventBusPort,
    GoalRecord,
    GoalRepositoryPort,
    KnowledgeIngestResult,
    KnowledgePort,
    LanguageModelPort,
    PlannerPort,
    UnitOfWorkPort,
)
from app.agentos.domain.events import DomainEvent


class GoalService:
    """Application use cases for AgentOS goals."""

    def __init__(
        self,
        *,
        planner: PlannerPort,
        goals: GoalRepositoryPort,
        events: EventBusPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self.planner = planner
        self.goals = goals
        self.events = events
        self.uow = uow

    def plan_goal(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        title: str,
        objective: str,
        mode: str = "resource-light",
    ) -> GoalRecord:
        try:
            plan = self.planner.plan(objective, mode=mode)
            item = self.goals.add(
                workspace_id=workspace_id,
                project_id=project_id,
                title=title,
                objective=objective,
                plan=plan,
            )
            self.events.publish(
                DomainEvent(
                    name="agentos.goal_planned",
                    workspace_id=workspace_id,
                    project_id=project_id,
                    payload={"goal_id": item.id, "steps": len(plan.steps), "mode": plan.mode},
                )
            )
            self.uow.commit()
            return item
        except Exception:
            self.uow.rollback()
            raise

    def get_goal(self, *, workspace_id: str, goal_id: str) -> GoalRecord | None:
        return self.goals.get(workspace_id=workspace_id, goal_id=goal_id)


class KnowledgeService:
    """Application use cases for ingestion and retrieval."""

    def __init__(
        self,
        *,
        knowledge: KnowledgePort,
        events: EventBusPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self.knowledge = knowledge
        self.events = events
        self.uow = uow

    def ingest(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        source: str,
        content: str,
        metadata: dict[str, Any],
    ) -> KnowledgeIngestResult:
        try:
            result = self.knowledge.ingest(
                workspace_id=workspace_id,
                project_id=project_id,
                namespace=namespace,
                source=source,
                content=content,
                metadata=metadata,
            )
            self.events.publish(
                DomainEvent(
                    name="agentos.knowledge_ingested",
                    workspace_id=workspace_id,
                    project_id=project_id,
                    payload={
                        "namespace": namespace,
                        "source": source,
                        "chunks": result.chunks,
                        "providers": result.providers,
                        "models": result.models,
                    },
                )
            )
            self.uow.commit()
            return result
        except Exception:
            self.uow.rollback()
            raise

    def search(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        return self.knowledge.search(
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            query=query,
            top_k=top_k,
        )


class ChatService:
    """RAG-backed chat use case independent of the concrete model provider."""

    def __init__(
        self,
        *,
        knowledge: KnowledgePort,
        model: LanguageModelPort,
        events: EventBusPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self.knowledge = knowledge
        self.model = model
        self.events = events
        self.uow = uow

    def answer(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        query: str,
        top_k: int,
        system: str,
    ) -> dict[str, Any]:
        matches = self.knowledge.search(
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            query=query,
            top_k=top_k,
        )
        context = "\n\n".join(
            f"[{index + 1}] {item['source']}: {item['content']}"
            for index, item in enumerate(matches)
        )
        messages = [
            {
                "role": "system",
                "content": system
                + "\nIf context is provided, ground factual claims in it and say when it is insufficient.",
            },
            {
                "role": "user",
                "content": f"Context:\n{context or '(no relevant context)'}\n\nQuestion:\n{query}",
            },
        ]

        try:
            result = self.model.chat(messages)
        except ModelUnavailable as error:
            self.events.publish(
                DomainEvent(
                    name="agentos.model_used",
                    workspace_id=workspace_id,
                    project_id=project_id,
                    outcome="failed",
                    payload={"operation": "chat", "error": str(error)},
                )
            )
            self.uow.commit()
            raise

        self.events.publish(
            DomainEvent(
                name="agentos.model_used",
                workspace_id=workspace_id,
                project_id=project_id,
                payload={
                    "operation": "chat",
                    "provider": result["provider"],
                    "model": result["model"],
                    "rag_matches": len(matches),
                },
            )
        )
        self.uow.commit()
        return {**result, "matches": matches}
