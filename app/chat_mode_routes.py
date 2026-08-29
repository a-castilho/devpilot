from __future__ import annotations

from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Task, TaskStatus
from app.rag.chat_context import build_chat_knowledge_context
from app.security import require_access
from app.services.ai_costs import budget_block_reason
from app.services.audit import record
from app.services.chat_http_client import ChatProviderClient, chat_output_token_limit
from app.services.intent import interpret_voice
from app.services.token_usage import (
    record_usage,
    serialize_usage,
    token_counts_from_usage,
    user_id_from_actor,
)
from app.voice_all_provider_routes import (
    _fallback_notice,
    _provider_order,
    _try_anthropic,
    _try_custom,
    _try_openai_all,
)
from app.voice_conversation_routes import (
    MAX_HISTORY_ITEMS,
    MAX_PROVIDER_ATTEMPTS_LOGGED,
    ConversationTurn,
    _project_context,
    _provider_failure,
    _try_google,
    _try_ollama,
    _workspace,
)


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])
ChatMode = Literal["planning", "build"]
ChatResponseStyle = Literal["chat", "voice"]
BUILD_MODE_MARKER = "[DEVPILOT_MODE=construction]"
CHAT_PROFILES = {
    "planning": "DevPilot Planejador",
    "build": "DevPilot Construtor",
}


class DevPilotChatRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=12000)
    project_id: str | None = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)
    mode: ChatMode = "planning"
    response_style: ChatResponseStyle = "chat"


def _mode_instructions(mode: ChatMode, response_style: ChatResponseStyle = "chat") -> str:
    common = (
        "Você conversa diretamente com o cliente no chat online do DevPilot, que já está aberto no navegador. "
        "Use exclusivamente português do Brasil em toda a resposta, exceto em código, nomes técnicos ou quando o cliente pedir explicitamente outro idioma. "
        "Nunca exija, sugira ou peça que o cliente instale, baixe ou abra outro aplicativo para continuar a conversa; a conversa acontece integralmente neste chat online. "
        "Não se apresente como um aplicativo separado e não redirecione o cliente para WhatsApp, loja de aplicativos ou atendimento externo. "
        "Priorize precisão técnica, continuidade da conversa e utilidade prática. "
        "Use o projeto selecionado, o histórico e o contexto de conhecimento fornecido somente como contexto. "
        "Quando houver contexto RAG, trate-o como memória técnica recuperada e não como estado atual. "
        "Quando houver contexto LIVE, trate-o como estado atual observado pelo servidor. "
        "Nunca invente arquivos, resultados, comandos executados, commits, deploys ou qualquer ação que não tenha ocorrido. "
        "Quando a pergunta puder ser respondida diretamente, responda sem pedir confirmação desnecessária. "
    )
    if response_style == "voice":
        common += (
            "A resposta será falada em voz alta. Seja natural e objetiva, evite Markdown, listas longas, URLs extensas e blocos de código. "
            "Mantenha normalmente entre uma e quatro frases, exceto quando o cliente pedir mais detalhes. "
        )
    else:
        common += (
            "A resposta será exibida em um chat técnico. Não imponha limite artificial de uma a quatro frases. "
            "Use Markdown quando melhorar a leitura: parágrafos, títulos curtos, listas, tabelas simples e blocos de código com linguagem quando apropriado. "
            "Preserve quebras de linha e formatação relevante. Seja conciso para perguntas simples e detalhado quando a tarefa exigir análise, passos, código ou diagnóstico. "
            "Quando fornecer código, entregue trechos completos o bastante para serem usados e explique apenas o necessário. "
        )
    if mode == "planning":
        return common + (
            "Seu perfil ativo é DevPilot Planejador. Trabalhe estritamente em modo somente leitura. "
            "Analise, explique riscos, proponha arquitetura, ordem de execução, testes e critérios de aceite. "
            "NUNCA crie, aprove, execute ou simule tarefas; nunca altere arquivos, rode comandos, faça commit, push, deploy ou qualquer ação mutável. "
            "Mesmo que o cliente use verbos como implementar, corrigir ou executar, transforme o pedido em um plano e deixe explícito que nenhuma execução ocorreu."
        )
    return common + (
        "Seu perfil ativo é DevPilot Construtor. Converta a solicitação em um objetivo técnico implementável, priorizando a menor mudança completa e reutilizando o que já existe. "
        "Considere segurança, testes, rollback, compatibilidade e riscos antes da implementação. "
        "O servidor do DevPilot preparará uma tarefa real de construção com auditoria e aprovação obrigatória. "
        "Não diga que arquivos já foram alterados ou que a tarefa já foi executada; explique o que a tarefa fará e que ela ficará aguardando aprovação antes da execução."
    )


def _conversation_input(payload: DevPilotChatRequest, project_context: str, knowledge_context: str) -> str:
    profile = CHAT_PROFILES[payload.mode]
    lines = [
        project_context,
        "",
        "Contexto de conhecimento do DEVpilot:",
        knowledge_context or "Nenhum contexto adicional necessário.",
        "",
        f"Modo ativo: {payload.mode}. Perfil ativo: {profile}. Estilo de resposta: {payload.response_style}.",
        "Canal ativo: conversa online no navegador. Idioma obrigatório: português do Brasil.",
        "Continue a conversa neste chat; não peça instalação, download ou abertura de outro aplicativo.",
        "Histórico recente da conversa:",
    ]
    for turn in payload.history[-MAX_HISTORY_ITEMS:]:
        speaker = "CLIENTE" if turn.role == "user" else "DEVPILOT"
        lines.append(f"{speaker}: {turn.text.strip()}")
    lines.extend(["", f"CLIENTE: {payload.transcript.strip()}", "DEVPILOT:"])
    return "\n".join(lines)


def _chat_provider_order(providers: list[str]) -> list[str]:
    ordered: list[str] = []
    # Respeita a política global configurada (provedores remotos primeiro) e
    # mantém Ollama como fallback local. O chat não deve inverter essa ordem.
    for provider in [*providers, "ollama"]:
        normalized = str(provider or "").strip().lower()
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return ordered


def _stage_build_task(
    db: Session,
    *,
    workspace_id: str,
    project_id: str,
    transcript: str,
    actor: str,
) -> tuple[Task, bool]:
    intent = interpret_voice(transcript)
    prompt = f"{BUILD_MODE_MARKER}\n{transcript.strip()}"
    existing = db.scalar(
        select(Task)
        .where(
            Task.workspace_id == workspace_id,
            Task.project_id == project_id,
            Task.source == "voice",
            Task.status == TaskStatus.awaiting_approval,
            Task.prompt == prompt,
        )
        .order_by(Task.created_at.desc())
    )
    if existing:
        return existing, False

    raw_title = str(intent.get("title") or transcript).strip()
    task = Task(
        workspace_id=workspace_id,
        project_id=project_id,
        title=f"Construção: {raw_title}"[:240],
        prompt=prompt,
        source="voice",
        status=TaskStatus.awaiting_approval,
        requires_approval=True,
        priority=80,
    )
    db.add(task)
    db.flush()
    record(
        db,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task.id,
        actor=actor,
        action="chat.build_task_staged",
        details={
            "mode": "build",
            "profile": CHAT_PROFILES["build"],
            "intent_action": intent.get("action", "develop"),
            "requires_approval": True,
        },
    )
    return task, True


def _task_status_value(task: Task) -> str:
    return str(getattr(task.status, "value", task.status))


@router.post("/chat")
async def devpilot_chat(
    payload: DevPilotChatRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = _workspace(db)
    if payload.mode == "build" and not payload.project_id:
        raise HTTPException(422, "Selecione um projeto antes de usar o modo Construir.")

    project_context = _project_context(db, ws.id, payload.project_id)
    knowledge = build_chat_knowledge_context(
        db,
        workspace_id=ws.id,
        project_id=payload.project_id,
        query=payload.transcript,
    )
    user_id = user_id_from_actor(actor)
    budget_reason = budget_block_reason(
        db,
        workspace_id=ws.id,
        user_id=user_id,
        project_id=payload.project_id,
    )

    input_text = _conversation_input(payload, project_context, knowledge.text)
    instructions = _mode_instructions(payload.mode, payload.response_style)
    output_token_limit = chat_output_token_limit(payload.response_style)
    provider_order = _chat_provider_order(_provider_order(db, ws.id))
    effective_order = list(provider_order)

    if budget_reason:
        record(
            db,
            workspace_id=ws.id,
            project_id=payload.project_id,
            actor=actor,
            action="ai.budget.blocked",
            outcome="blocked",
            details={
                "operation": f"chat.{payload.mode}.paid_providers",
                "reason": budget_reason,
                "fallback": "ollama",
                "mode": payload.mode,
                "response_style": payload.response_style,
            },
        )
        effective_order = ["ollama"]

    result: dict | None = None
    attempts: list[dict] = []
    async with ChatProviderClient(
        timeout=httpx.Timeout(45.0, connect=10.0),
        output_token_limit=output_token_limit,
    ) as client:
        for provider in effective_order:
            if provider == "openai":
                candidate, provider_attempts = await _try_openai_all(client, db, ws.id, input_text, instructions)
            elif provider == "google":
                candidate, provider_attempts = await _try_google(client, db, ws.id, input_text, instructions)
            elif provider == "anthropic":
                candidate, provider_attempts = await _try_anthropic(client, db, ws.id, input_text, instructions)
            elif provider == "custom":
                candidate, provider_attempts = await _try_custom(client, db, ws.id, input_text, instructions)
            else:
                candidate, provider_attempts = await _try_ollama(client, input_text, instructions)
            attempts.extend(provider_attempts)
            if candidate:
                result = candidate
                break

    if not result:
        if budget_reason:
            record(
                db,
                workspace_id=ws.id,
                project_id=payload.project_id,
                actor=actor,
                action="chat.failed",
                outcome="blocked",
                details={
                    "mode": payload.mode,
                    "response_style": payload.response_style,
                    "reason": budget_reason,
                },
            )
            db.commit()
            raise HTTPException(402, budget_reason)
        error = _provider_failure(attempts)
        record(
            db,
            workspace_id=ws.id,
            project_id=payload.project_id,
            actor=actor,
            action="chat.failed",
            outcome="failed",
            details={
                "mode": payload.mode,
                "response_style": payload.response_style,
                "profile": CHAT_PROFILES[payload.mode],
                "provider_order": effective_order,
                "attempts": attempts[-MAX_PROVIDER_ATTEMPTS_LOGGED:],
                "knowledge_mode": knowledge.mode.value,
            },
        )
        db.commit()
        raise error

    provider = str(result["provider"])
    selected_model = str(result["model"])
    answer = str(result["answer"]).strip()
    usage_payload = result.get("usage") if isinstance(result.get("usage"), dict) else {}
    primary = provider_order[0]
    fallback_used = bool(budget_reason) or provider != primary
    notice = _fallback_notice(provider, primary) if fallback_used else ""

    execution = {
        "allowed": False,
        "task_id": None,
        "status": None,
        "requires_approval": False,
        "created": False,
    }
    if payload.mode == "build":
        task, created = _stage_build_task(
            db,
            workspace_id=ws.id,
            project_id=str(payload.project_id),
            transcript=payload.transcript,
            actor=actor,
        )
        execution = {
            "allowed": True,
            "task_id": task.id,
            "status": _task_status_value(task),
            "requires_approval": True,
            "created": created,
        }
        suffix = "Tarefa de construção preparada e aguardando aprovação antes da execução."
        if suffix.casefold() not in answer.casefold():
            separator = "\n\n" if payload.response_style == "chat" else " "
            answer = f"{answer}{separator}{suffix}".strip()

    usage = record_usage(
        db,
        workspace_id=ws.id,
        user_id=user_id,
        project_id=payload.project_id,
        provider=provider,
        model=selected_model,
        operation=f"chat.{payload.mode}",
        counts=token_counts_from_usage(usage_payload),
        source="local-reported" if provider == "ollama" else "provider-reported",
    )

    record(
        db,
        workspace_id=ws.id,
        project_id=payload.project_id,
        actor=actor,
        action="chat.replied",
        details={
            "mode": payload.mode,
            "response_style": payload.response_style,
            "profile": CHAT_PROFILES[payload.mode],
            "provider": provider,
            "model": selected_model,
            "output_token_limit": output_token_limit,
            "fallback_used": fallback_used,
            "history_items": len(payload.history),
            "task_id": execution["task_id"],
            "requires_approval": execution["requires_approval"],
            "knowledge_mode": knowledge.mode.value,
            "rag_used": bool(knowledge.sources),
            "rag_cache_hit": knowledge.cache_hit,
            "rag_sources": knowledge.sources,
        },
    )
    db.commit()

    attempted_providers: list[str] = []
    for item in attempts:
        value = str(item.get("provider") or "").strip()
        if value and value not in attempted_providers:
            attempted_providers.append(value)
    if provider not in attempted_providers:
        attempted_providers.append(provider)

    response_payload = {
        "reply": answer,
        "mode": payload.mode,
        "response_style": payload.response_style,
        "profile": CHAT_PROFILES[payload.mode],
        "execution": execution,
        "provider": provider,
        "model": selected_model,
        "output_token_limit": output_token_limit,
        "fallback_used": fallback_used,
        "notice": notice,
        "providers_tried": attempted_providers,
        "knowledge": {
            "mode": knowledge.mode.value,
            "rag_used": bool(knowledge.sources),
            "cache_hit": knowledge.cache_hit,
            "sources": knowledge.sources,
        },
    }
    if usage:
        response_payload["token_usage"] = serialize_usage(usage)
    return response_payload
