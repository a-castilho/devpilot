from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Project, Run, Task, TaskStatus

from .runtime import get_rag_service
from .scope import project_rag_scope
from .service import RagQueryMode, RetrievalResult


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChatKnowledgeContext:
    mode: RagQueryMode
    text: str
    sources: list[dict[str, Any]]
    cache_hit: bool = False


def _live_context(db: Session, workspace_id: str, project_id: str | None) -> str:
    task_filters = [Task.workspace_id == workspace_id]
    if project_id:
        task_filters.append(Task.project_id == project_id)

    total = db.scalar(select(func.count(Task.id)).where(*task_filters)) or 0
    queued = db.scalar(select(func.count(Task.id)).where(*task_filters, Task.status == TaskStatus.queued)) or 0
    running = db.scalar(select(func.count(Task.id)).where(*task_filters, Task.status == TaskStatus.running)) or 0
    blocked = db.scalar(select(func.count(Task.id)).where(*task_filters, Task.status == TaskStatus.blocked)) or 0
    failed = db.scalar(select(func.count(Task.id)).where(*task_filters, Task.status == TaskStatus.failed)) or 0
    awaiting = db.scalar(select(func.count(Task.id)).where(*task_filters, Task.status == TaskStatus.awaiting_approval)) or 0

    scope = f"projeto {project_id}" if project_id else "workspace atual"
    return (
        f"Estado atual do {scope}: tarefas={total}, fila={queued}, executando={running}, "
        f"aguardando_aprovacao={awaiting}, bloqueadas={blocked}, falhas={failed}."
    )


def _project_memory_context(db: Session, workspace_id: str, project_id: str | None) -> str:
    if not project_id:
        return ""
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if not project:
        return ""

    lines = [
        "Contexto persistente do projeto:",
        f"Nome: {project.name}",
        f"Descrição: {(project.description or '').strip() or 'Sem descrição cadastrada.'}",
        f"Repositório: {project.repository_url}",
        f"Branch padrão: {project.default_branch}",
        f"Escopo RAG: {'organização' if project.organization_id else 'workspace'}",
    ]

    agents = (project.agents_md or "").strip()
    if agents:
        lines.extend(["", "Documentação/instruções persistentes (AGENTS.md):", agents[:7000]])

    recent_tasks = list(
        db.scalars(
            select(Task)
            .where(Task.workspace_id == workspace_id, Task.project_id == project.id)
            .order_by(Task.updated_at.desc())
            .limit(6)
        ).all()
    )
    if recent_tasks:
        lines.extend(["", "Atividades recentes do projeto:"])
        for task in recent_tasks:
            status = str(getattr(task.status, "value", task.status))
            lines.append(f"- {task.title} [{status}]")

        task_ids = [task.id for task in recent_tasks]
        recent_runs = list(
            db.scalars(
                select(Run)
                .where(Run.task_id.in_(task_ids))
                .order_by(Run.started_at.desc())
                .limit(4)
            ).all()
        )
        summaries = [" ".join((run.summary or "").split())[:800] for run in recent_runs if (run.summary or "").strip()]
        if summaries:
            lines.extend(["", "Resultados recentes documentados:"])
            lines.extend(f"- {summary}" for summary in summaries)

    return "\n".join(lines)[:12000]


def _rag_context(result: RetrievalResult) -> tuple[str, list[dict[str, Any]]]:
    if not result.chunks:
        return "Memória RAG: nenhum trecho relevante recuperado.", []

    lines = ["Memória técnica recuperada pelo RAG:"]
    sources: list[dict[str, Any]] = []
    for index, chunk in enumerate(result.chunks, start=1):
        source = chunk.source_path or chunk.source_id or chunk.id
        content = " ".join(chunk.content.split())[:1800]
        lines.append(f"[{index}] {source} (score={chunk.score:.3f}): {content}")
        sources.append(
            {
                "id": chunk.id,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "source_path": chunk.source_path,
                "score": chunk.score,
            }
        )
    return "\n".join(lines), sources


def build_chat_knowledge_context(
    db: Session,
    *,
    workspace_id: str,
    project_id: str | None,
    query: str,
) -> ChatKnowledgeContext:
    rag = get_rag_service()
    mode = rag.router.classify(query)
    parts: list[str] = []
    sources: list[dict[str, Any]] = []
    cache_hit = False

    project_memory = _project_memory_context(db, workspace_id, project_id)
    if project_memory:
        parts.append(project_memory)

    # O chat sempre recebe estado operacional quando existe projeto. Isto faz
    # perguntas naturais como "o que está acontecendo?" funcionarem sem exigir
    # palavras-chave específicas do roteador RAG.
    if project_id or mode in {RagQueryMode.LIVE, RagQueryMode.RAG_LIVE}:
        parts.append(_live_context(db, workspace_id, project_id))

    if mode in {RagQueryMode.RAG, RagQueryMode.RAG_LIVE} and project_id:
        project = db.scalar(
            select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        )
        if project:
            scope_id = project_rag_scope(project)
            try:
                result = rag.retrieve(
                    organization_id=scope_id,
                    project_id=project.id,
                    query=query,
                )
            except Exception as exc:
                logger.warning("RAG retrieval unavailable for project %s: %s", project.id, type(exc).__name__)
                parts.append("Memória RAG temporariamente indisponível; o chat continua com documentação e estado do projeto.")
            else:
                rag_text, sources = _rag_context(result)
                parts.append(rag_text)
                cache_hit = result.cache_hit
        else:
            parts.append("Memória RAG não consultada: projeto não encontrado no workspace atual.")
    elif mode in {RagQueryMode.RAG, RagQueryMode.RAG_LIVE}:
        parts.append("Memória RAG não consultada: nenhum projeto foi selecionado.")

    return ChatKnowledgeContext(
        mode=mode,
        text="\n\n".join(part for part in parts if part),
        sources=sources,
        cache_hit=cache_hit,
    )
