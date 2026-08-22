from __future__ import annotations

import json
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, ProviderCredential, Workspace
from app.security import require_access
from app.services.ai_costs import budget_block_reason
from app.services.audit import record
from app.services.token_usage import (
    record_usage,
    serialize_usage,
    token_counts_from_usage,
    user_id_from_actor,
)
from app.services.vault import Vault


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])

DEFAULT_CHAT_MODELS = ("gpt-5.6", "gpt-5", "gpt-4.1-mini")
MAX_HISTORY_ITEMS = 12


class ConversationTurn(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    text: str = Field(min_length=1, max_length=4000)


class VoiceConversationRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)
    project_id: str | None = None
    history: list[ConversationTurn] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if item:
        return item
    item = Workspace(name="DevPilot", slug="default")
    db.add(item)
    db.flush()
    return item


def _decrypt_secret(item: ProviderCredential) -> str:
    try:
        return Vault().decrypt(item.encrypted_secret).strip()
    except Exception:
        return ""


def _openai_api_keys(db: Session, workspace_id: str) -> list[str]:
    values = [os.getenv("OPENAI_API_KEY", "").strip()]
    credentials = db.scalars(
        select(ProviderCredential)
        .where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == "openai",
            ProviderCredential.enabled.is_(True),
        )
        .order_by(ProviderCredential.created_at.desc())
    ).all()
    values.extend(_decrypt_secret(item) for item in credentials)

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _chat_models() -> list[str]:
    configured = os.getenv("DEVPILOT_VOICE_CHAT_MODEL", "").strip()
    values = [configured, *DEFAULT_CHAT_MODELS]
    return list(dict.fromkeys(value for value in values if value))


def _project_context(db: Session, workspace_id: str, project_id: str | None) -> str:
    if not project_id:
        return "Nenhum projeto foi selecionado. Converse em nível geral e peça contexto somente quando necessário."
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if not project:
        raise HTTPException(404, "Projeto não encontrado")
    description = (project.description or "").strip() or "Sem descrição cadastrada."
    return (
        f"Projeto selecionado: {project.name}. "
        f"Descrição: {description}. "
        f"Repositório: {project.repository_url}. "
        f"Branch padrão: {project.default_branch}."
    )


def _conversation_input(payload: VoiceConversationRequest, project_context: str) -> str:
    lines = [project_context, "", "Histórico recente da conversa:"]
    for turn in payload.history[-MAX_HISTORY_ITEMS:]:
        speaker = "CLIENTE" if turn.role == "user" else "DEVPILOT"
        lines.append(f"{speaker}: {turn.text.strip()}")
    lines.extend(["", f"CLIENTE: {payload.transcript.strip()}", "DEVPILOT:"])
    return "\n".join(lines)


def _response_text(data: dict) -> str:
    direct = str(data.get("output_text") or "").strip()
    if direct:
        return direct
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text":
                text = str(content.get("text") or "").strip()
                if text:
                    return text
    return ""


def _provider_failure(statuses: list[int]) -> HTTPException:
    if 429 in statuses:
        return HTTPException(429, "Limite da conversa por voz atingido. Tente novamente em instantes.")
    if statuses and all(status in {401, 403} for status in statuses):
        return HTTPException(503, "A credencial OpenAI não está válida para a conversa por voz.")
    return HTTPException(502, "O DevPilot não conseguiu responder por voz agora.")


@router.post("/voice/chat")
async def voice_chat(
    payload: VoiceConversationRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    ws = _workspace(db)
    project_context = _project_context(db, ws.id, payload.project_id)
    user_id = user_id_from_actor(actor)
    budget_reason = budget_block_reason(
        db,
        workspace_id=ws.id,
        user_id=user_id,
        project_id=payload.project_id,
    )
    if budget_reason:
        record(
            db,
            workspace_id=ws.id,
            project_id=payload.project_id,
            actor=actor,
            action="ai.budget.blocked",
            outcome="blocked",
            details={"operation": "voice.chat", "reason": budget_reason},
        )
        db.commit()
        raise HTTPException(402, budget_reason)

    keys = _openai_api_keys(db, ws.id)
    if not keys:
        raise HTTPException(
            503,
            "Nenhuma credencial OpenAI ativa está disponível para a conversa por voz.",
        )

    input_text = _conversation_input(payload, project_context)
    instructions = (
        "Você é o DevPilot, consultor de desenvolvimento que conversa diretamente com o cliente. "
        "Responda sempre em português do Brasil, de forma natural, objetiva e própria para ser falada em voz alta. "
        "Entenda a intenção antes de sugerir implementação. Faça no máximo uma pergunta quando faltar informação essencial. "
        "Quando o cliente pedir uma alteração, explique brevemente o que será feito e o próximo passo. "
        "Não invente que uma alteração foi executada se ela ainda não foi executada. "
        "Evite Markdown, listas longas, URLs e blocos de código na resposta falada. "
        "Mantenha a resposta normalmente entre uma e quatro frases."
    )

    statuses: list[int] = []
    selected_model = ""
    answer = ""
    usage_payload: dict = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
        for api_key in keys:
            for model in _chat_models():
                try:
                    response = await client.post(
                        "https://api.openai.com/v1/responses",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "instructions": instructions,
                            "input": input_text,
                            "max_output_tokens": 280,
                            "store": False,
                        },
                    )
                except httpx.HTTPError:
                    statuses.append(502)
                    continue

                if response.status_code >= 400:
                    statuses.append(response.status_code)
                    continue

                try:
                    data = response.json()
                except ValueError:
                    statuses.append(502)
                    continue

                answer = _response_text(data)
                if answer:
                    selected_model = model
                    raw_usage = data.get("usage")
                    usage_payload = raw_usage if isinstance(raw_usage, dict) else {}
                    break
                statuses.append(502)
            if answer:
                break

    if not answer:
        error = _provider_failure(statuses)
        record(
            db,
            workspace_id=ws.id,
            project_id=payload.project_id,
            actor=actor,
            action="voice.chat_failed",
            outcome="failed",
            details={"statuses": statuses[-8:], "history_items": len(payload.history)},
        )
        db.commit()
        raise error

    usage = record_usage(
        db,
        workspace_id=ws.id,
        user_id=user_id,
        project_id=payload.project_id,
        provider="openai",
        model=selected_model,
        operation="voice.chat",
        counts=token_counts_from_usage(usage_payload),
    )
    record(
        db,
        workspace_id=ws.id,
        project_id=payload.project_id,
        actor=actor,
        action="voice.chat_replied",
        details={
            "provider": "openai",
            "model": selected_model,
            "input_characters": len(payload.transcript),
            "output_characters": len(answer),
            "history_items": len(payload.history),
        },
    )
    db.commit()

    result = {"reply": answer, "provider": "openai", "model": selected_model}
    if usage:
        result["token_usage"] = serialize_usage(usage)
    return result
