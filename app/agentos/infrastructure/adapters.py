from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.errors import ModelUnavailable as ApplicationModelUnavailable
from app.agentos.application.planning import PlanningStrategyFactory
from app.agentos.application.ports import GoalRecord, KnowledgeIngestResult
from app.agentos.contracts import AgentPlan
from app.agentos.domain.events import DomainEvent
from app.agentos.llm import LLMClient, ModelUnavailable as ProviderModelUnavailable
from app.agentos.models import AgentGoal
from app.agentos.rag import ingest as rag_ingest
from app.agentos.rag import search as rag_search
from app.config import get_settings
from app.models import ProviderCredential, Workspace
from app.services.audit import record
from app.services.provider_runtime import ProviderRuntimeError, run_provider_chat
from app.services.vault import Vault


class PlannerAdapter:
    """Adapter from the application planner port to a selectable planning strategy."""

    def plan(self, objective: str, *, mode: str = "resource-light") -> AgentPlan:
        return PlanningStrategyFactory.create(mode).plan(objective)


class SQLAlchemyGoalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _record(item: AgentGoal) -> GoalRecord:
        return GoalRecord(
            id=item.id,
            workspace_id=item.workspace_id,
            project_id=item.project_id,
            title=item.title,
            objective=item.objective,
            status=item.status,
            plan=AgentPlan.model_validate_json(item.plan_json),
            created_at=item.created_at,
        )

    def add(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        title: str,
        objective: str,
        plan: AgentPlan,
    ) -> GoalRecord:
        item = AgentGoal(
            workspace_id=workspace_id,
            project_id=project_id,
            title=title,
            objective=objective,
            status="planned",
            plan_json=plan.model_dump_json(),
        )
        self.db.add(item)
        self.db.flush()
        return self._record(item)

    def get(self, *, workspace_id: str, goal_id: str) -> GoalRecord | None:
        item = self.db.scalar(
            select(AgentGoal).where(
                AgentGoal.id == goal_id,
                AgentGoal.workspace_id == workspace_id,
            )
        )
        return self._record(item) if item else None


class SQLAlchemyKnowledgeAdapter:
    """Adapter around the existing SQLite/PostgreSQL RAG persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db

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
        chunks = rag_ingest(
            self.db,
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            source=source,
            content=content,
            metadata=metadata,
        )
        return KnowledgeIngestResult(
            ids=[item.id for item in chunks],
            models=sorted({item.embedding_model for item in chunks}),
            providers=sorted({item.embedding_provider for item in chunks}),
        )

    def search(
        self,
        *,
        workspace_id: str,
        project_id: str | None,
        namespace: str,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        return rag_search(
            self.db,
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            query=query,
            top_k=top_k,
        )


class OllamaLanguageModelAdapter:
    """Adapter pattern: hides the provider-specific Ollama client behind a stable port."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or LLMClient()

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        try:
            return self.client.chat(messages)
        except ProviderModelUnavailable as error:
            raise ApplicationModelUnavailable(str(error)) from error


class ConfiguredLanguageModelAdapter:
    """Resolve AgentOS text generation to Ollama or an encrypted saved provider connection.

    External-provider selection is explicit through DEVPILOT_AGENTOS_MODEL_PROVIDER and optional
    connection/model selectors. The adapter stays workspace-scoped to the current default workspace.
    A configured Ollama fallback is used only for transient provider/network failures; credential,
    model and configuration errors fail closed instead of silently switching providers.
    """

    SUPPORTED_EXTERNAL = {"openai", "anthropic", "google"}

    def __init__(self, db: Session, *, ollama: OllamaLanguageModelAdapter | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self.ollama = ollama or OllamaLanguageModelAdapter()

    @staticmethod
    def _stored_models(item: ProviderCredential) -> list[str]:
        try:
            values = json.loads(item.models or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value).strip()]

    def _connection(self, provider: str) -> ProviderCredential:
        ws = self.db.scalar(select(Workspace).where(Workspace.slug == "default"))
        if not ws:
            raise ApplicationModelUnavailable("Workspace padrão do AgentOS não encontrado.")

        query = select(ProviderCredential).where(
            ProviderCredential.workspace_id == ws.id,
            ProviderCredential.provider == provider,
            ProviderCredential.enabled.is_(True),
        )
        label = self.settings.agentos_model_connection_label.strip()
        if label:
            query = query.where(ProviderCredential.label == label)
        item = self.db.scalar(query.order_by(ProviderCredential.created_at.desc()).limit(1))
        if not item:
            suffix = f" com o nome {label!r}" if label else ""
            raise ApplicationModelUnavailable(
                f"Nenhuma conexão {provider} ativa{suffix} está configurada para o AgentOS."
            )
        return item

    def _external_chat(self, provider: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        item = self._connection(provider)
        models = self._stored_models(item)
        configured_model = self.settings.agentos_model_name.strip()
        model = configured_model or (models[0] if models else "")
        if not model:
            raise ApplicationModelUnavailable("A conexão de IA não possui modelo configurado.")
        if models and configured_model and configured_model not in models:
            raise ApplicationModelUnavailable(
                f"O modelo {configured_model!r} não pertence à conexão selecionada."
            )

        try:
            secret = Vault().decrypt(item.encrypted_secret)
        except (RuntimeError, ValueError) as error:
            raise ApplicationModelUnavailable(
                "A credencial do provedor não pôde ser aberta pelo cofre do DevPilot."
            ) from error

        try:
            result = run_provider_chat(
                provider,
                secret,
                model,
                messages,
                timeout_seconds=self.settings.model_timeout_seconds,
                max_output_tokens=self.settings.agentos_model_max_output_tokens,
            )
        except ProviderRuntimeError as error:
            fallback = self.settings.agentos_model_fallback.strip().lower()
            if error.retryable and fallback == "ollama":
                local = self.ollama.chat(messages)
                return {
                    **local,
                    "fallback_from": provider,
                    "fallback_reason": "transient_provider_failure",
                }
            raise ApplicationModelUnavailable(str(error)) from error

        return {
            "content": result.reply,
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
        }

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        provider = self.settings.agentos_model_provider.strip().lower() or "ollama"
        if provider == "ollama":
            return self.ollama.chat(messages)
        if provider not in self.SUPPORTED_EXTERNAL:
            raise ApplicationModelUnavailable(
                f"Provedor AgentOS não suportado: {provider!r}."
            )
        return self._external_chat(provider, messages)


class SQLAlchemyUnitOfWork:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


EventHandler = Callable[[DomainEvent], None]


class LocalEventBus:
    """In-process event bus using Observer/Pub-Sub without extra RAM-heavy infrastructure."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event: DomainEvent) -> None:
        handlers = [*self._handlers.get(event.name, []), *self._handlers.get("*", [])]
        for handler in handlers:
            handler(event)


class AuditEventHandler:
    """Observer that maps AgentOS domain events onto the existing audit hash-chain."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def __call__(self, event: DomainEvent) -> None:
        details = dict(event.payload)
        details.setdefault("occurred_at", event.occurred_at.isoformat())
        record(
            self.db,
            workspace_id=event.workspace_id,
            project_id=event.project_id,
            task_id=event.task_id,
            actor=event.actor,
            action=event.name,
            outcome=event.outcome,
            details=details,
        )
