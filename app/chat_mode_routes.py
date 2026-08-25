from __future__ import annotations

from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Task, TaskStatus
from app.security import require_access
from app.services.ai_costs import budget_block_reason
from app.services.audit import record
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
BUILD_MODE_MARKER = "[DEVPILOT_MODE=construction]"
CHAT_PROFILES = {
    "planning": "DevPilot Planejador",
    "build": "DevPilot Construtor",
}


class DevPilotChatRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)
    project_id: str | None = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)
    mode: ChatMode = "planning"


def _mode_instructions(mode: ChatMode) -> str:
    common = (
        "Você conversa diretamente com o cliente dentro do DevPilot. "
        "Responda sempre em português do Brasil, de forma natural, objetiva e própria para ser falada em voz alta. "
        "Use o projeto selecionado e o histórico somente como contexto. "
        "Nunca invente que uma ação ocorreu. Evite Markdown, listas longas, URLs e blocos de código. "
        "Mantenha a resposta normalmente entre uma e quatro frases. "
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
        "Não diga que arquivos já foram alterados ou que a tarefa já foi executada; explique de forma curta o que a tarefa fará e que ela ficará aguardando aprovação antes da execução."
    )


def _conversation_input(payload: DevPilotChatRequest, project_context: str) -> str:
    profile = CHAT_PROFILES[payload.mode]
    lines = [
        project_context,
        "",
        f"Modo ativo: {payload.mode}. Perfil ativo: {profile}.",
        "Histórico recente da conversa:",
    ]
    for turn in payload.history[-MAX_HISTORY_ITEMS:]:
        speaker = "CLIENTE" if turn.role == "user" else "DEVPILOT"
        lines.append(f"{speaker}: {turn.text.strip()}")
    lines.extend(["", f"CLIENTE: {payload.transcript.strip()}", "DEVPILOT:"])
    return "\n".join(lines)


def _chat_provider_order(providers: list[str]) -> list[str]:
    """Keep interactive chat responsive by trying the local runtime first."""
    ordered: list[str] = []
    for provider in ["ollama", *providers]:
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
    title = f"Construção: {raw_title}"[:240]
    task = Task(
        workspace_id=workspace_id,
        project_id=project_id,
        title=title,
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
    value = task.status
    return str(getattr(value, "value", value))


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
    user_id = user_id_from_actor(actor)
    budget_reason = budget_block_reason(
        db,
        workspace_id=ws.id,
        user_id=user_id,
        project_id=payload.project_id,
    )

    input_text = _conversation_input(payload, project_context)
    instructions = _mode_instructions(payload.mode)
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
            },
        )
        effective_order = ["ollama"]

    result: dict | None = None
    attempts: list[dict] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
        for provider in effective_order:
            if provider == "openai":
                candidate, provider_attempts = await _try_openai_all(
                    client, db, ws.id, input_text, instructions
                )
            elif provider == "google":
                candidate, provider_attempts = await _try_google(
                    client, db, ws.id, input_text, instructions
                )
            elif provider == "anthropic":
                candidate, provider_attempts = await _try_anthropic(
                    client, db, ws.id, input_text, instructions
                )
            elif provider == "custom":
                candidate, provider_attempts = await _try_custom(
                    client, db, ws.id, input_text, instructions
                )
            else:
                candidate, provider_attempts = await _try_ollama(
                    client, input_text, instructions
                )

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
                    "profile": CHAT_PROFILES[payload.mode],
                    "reason": budget_reason,
                    "provider_order": effective_order,
                    "attempts": attempts[-MAX_PROVIDER_ATTEMPTS_LOGGED:],
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
                "profile": CHAT_PROFILES[payload.mode],
                "provider_order": effective_order,
                "attempts": attempts[-MAX_PROVIDER_ATTEMPTS_LOGGED:],
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
            answer = f"{answer} {suffix}".strip()

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
            "profile": CHAT_PROFILES[payload.mode],
            "provider": provider,
            "model": selected_model,
            "fallback_used": fallback_used,
            "history_items": len(payload.history),
            "task_id": execution["task_id"],
            "requires_approval": execution["requires_approval"],
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
        "profile": CHAT_PROFILES[payload.mode],
        "execution": execution,
        "provider": provider,
        "model": selected_model,
        "fallback_used": fallback_used,
        "notice": notice,
        "providers_tried": attempted_providers,
    }
    if usage:
        response_payload["token_usage"] = serialize_usage(usage)
    return response_payload
