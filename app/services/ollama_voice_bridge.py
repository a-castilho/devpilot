from __future__ import annotations

import asyncio
import json

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ProviderCredential
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError
from app.services.ollama_git_context import build_ollama_git_context


def _registered_models() -> list[str]:
    with SessionLocal() as db:
        items = db.scalars(
            select(ProviderCredential)
            .where(
                ProviderCredential.provider == "ollama",
                ProviderCredential.enabled.is_(True),
            )
            .order_by(ProviderCredential.created_at.desc())
        ).all()
        result: list[str] = []
        for item in items:
            try:
                values = json.loads(item.models or "[]")
            except (TypeError, ValueError):
                continue
            if not isinstance(values, list):
                continue
            for value in values:
                model = str(value or "").strip()
                if model and model not in result:
                    result.append(model)
        return result


async def try_registered_ollama(
    client,
    input_text: str,
    instructions: str,
) -> tuple[dict | None, list[dict]]:
    del client  # Ollama is intentionally reached through the signed Linux Agent.
    configured = _registered_models()
    if not configured:
        return None, [
            {
                "provider": "ollama",
                "model": "",
                "status": 0,
                "error_code": "not_configured",
            }
        ]

    git_context = await asyncio.to_thread(build_ollama_git_context, input_text)
    ollama_input = input_text
    ollama_instructions = instructions
    if git_context:
        ollama_input = (
            f"{input_text}\n\n{git_context}\n\n"
            "Use o contexto Git acima como evidência real e somente leitura do projeto selecionado. "
            "Quando ele indicar indisponibilidade, deixe claro que o Git não pôde ser lido e não invente conteúdo."
        )
        ollama_instructions = (
            f"{instructions} "
            "Quando houver CONTEXTO GIT SOMENTE LEITURA, responda com base nele e diferencie fatos lidos do Git "
            "de sugestões. Nunca diga que alterou arquivos apenas por ter lido o repositório."
        )

    agent = LinuxAgentClient()
    agent.timeout = 65.0
    try:
        runtime = await asyncio.to_thread(
            agent.request,
            "POST",
            "/v1/ollama/ensure",
            payload={},
        )
    except LinuxAgentError as error:
        return None, [
            {
                "provider": "ollama",
                "model": "linux-agent",
                "status": error.status_code,
                "error_type": type(error).__name__,
                "error_code": "linux_agent_unreachable",
            }
        ]

    installed = [str(value).strip() for value in runtime.get("models") or [] if str(value).strip()]
    models = [model for model in configured if model in installed]
    if not models:
        return None, [
            {
                "provider": "ollama",
                "model": "",
                "status": 503,
                "error_code": "configured_models_not_installed",
            }
        ]

    attempts: list[dict] = []
    for model in models[:5]:
        try:
            data = await asyncio.to_thread(
                agent.request,
                "POST",
                "/v1/ollama/chat",
                payload={
                    "model": model,
                    "instructions": ollama_instructions,
                    "input_text": ollama_input,
                },
            )
        except LinuxAgentError as error:
            attempts.append(
                {
                    "provider": "ollama",
                    "model": model,
                    "status": error.status_code,
                    "error_type": type(error).__name__,
                    "error_code": "linux_agent_chat_failed",
                }
            )
            continue

        answer = str(data.get("answer") or "").strip()
        if not answer:
            attempts.append(
                {
                    "provider": "ollama",
                    "model": model,
                    "status": 502,
                    "error_code": "empty_response",
                }
            )
            continue
        input_tokens = int(data.get("input_tokens") or 0)
        output_tokens = int(data.get("output_tokens") or 0)
        return {
            "answer": answer,
            "provider": "ollama",
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        }, attempts

    return None, attempts


def install_voice_ollama_bridge() -> None:
    from app import voice_conversation_routes

    voice_conversation_routes._try_ollama = try_registered_ollama
