from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine, get_db
from app.models import (
    AuditEvent,
    Organization,
    Project,
    ProviderCredential,
    Repository,
    Run,
    Task,
    TokenUsage,
    User,
    Workspace,
)
from app.security import require_super_admin


router = APIRouter(
    prefix="/api/super-admin/voice",
    tags=["super-admin-voice"],
    dependencies=[Depends(require_super_admin)],
)


def _workspace(db: Session) -> Workspace | None:
    return db.scalar(select(Workspace).where(Workspace.slug == "default"))


def _models(item: ProviderCredential) -> list[str]:
    try:
        raw = json.loads(item.models or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [str(value).strip() for value in raw if str(value).strip()]


def _details(event: AuditEvent | None) -> dict:
    if not event:
        return {}
    try:
        value = json.loads(event.details or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _has_env(*names: str) -> bool:
    return any(bool(os.getenv(name, "").strip()) for name in names)


def _count(db: Session, model, *filters) -> int:
    query = select(func.count(model.id))
    if filters:
        query = query.where(*filters)
    return int(db.scalar(query) or 0)


@router.get("/system-map")
def system_map_dashboard(db: Session = Depends(get_db)):
    """Return a secret-free, evidence-backed architecture map for SUPER_ADMIN."""
    ws = _workspace(db)
    now = datetime.now(timezone.utc)
    if not ws:
        return {
            "generated_at": now,
            "summary": {},
            "flow": [],
            "nodes": [],
            "edges": [],
            "warnings": ["Workspace padrão ainda não foi criado."],
        }

    settings = get_settings()
    users_total = _count(db, User, User.workspace_id == ws.id)
    users_active = _count(db, User, User.workspace_id == ws.id, User.active.is_(True))
    organizations_total = _count(db, Organization, Organization.workspace_id == ws.id)
    organization_errors = _count(
        db,
        Organization,
        Organization.workspace_id == ws.id,
        Organization.last_sync_error != "",
    )
    repositories_total = int(
        db.scalar(
            select(func.count(Repository.id))
            .join(Organization, Repository.organization_id == Organization.id)
            .where(Organization.workspace_id == ws.id)
        )
        or 0
    )
    projects_total = _count(db, Project, Project.workspace_id == ws.id)
    tasks_total = _count(db, Task, Task.workspace_id == ws.id)

    task_rows = db.execute(
        select(Task.status, func.count(Task.id))
        .where(Task.workspace_id == ws.id)
        .group_by(Task.status)
    ).all()
    task_counts = {
        getattr(status, "value", str(status)): int(total or 0)
        for status, total in task_rows
    }
    active_task_states = {"queued", "planning", "awaiting_approval", "running", "review", "blocked"}
    tasks_active = sum(task_counts.get(name, 0) for name in active_task_states)
    tasks_failed = task_counts.get("failed", 0)

    runs_active = int(
        db.scalar(
            select(func.count(Run.id))
            .join(Task, Run.task_id == Task.id)
            .where(Task.workspace_id == ws.id, Run.status.in_(("started", "running")))
        )
        or 0
    )

    credentials = list(
        db.scalars(
            select(ProviderCredential)
            .where(ProviderCredential.workspace_id == ws.id)
            .order_by(ProviderCredential.created_at.desc())
        ).all()
    )
    providers_enabled = [item for item in credentials if item.enabled]
    provider_names = sorted({item.provider for item in providers_enabled})

    since = now - timedelta(hours=24)
    audit_24h = _count(
        db,
        AuditEvent,
        AuditEvent.workspace_id == ws.id,
        AuditEvent.created_at >= since,
    )
    audit_failed_24h = _count(
        db,
        AuditEvent,
        AuditEvent.workspace_id == ws.id,
        AuditEvent.created_at >= since,
        AuditEvent.outcome == "failed",
    )

    db_backend = engine.url.get_backend_name()
    worker_enabled = bool(settings.execution_enabled or settings.embedded_worker or runs_active)
    worker_detail = (
        f"{runs_active} execução(ões) ativa(s)"
        if runs_active
        else "execução habilitada" if settings.execution_enabled
        else "worker embutido habilitado" if settings.embedded_worker
        else "sem execução ativa confirmada"
    )

    nodes = [
        {
            "id": "web",
            "group": "interfaces",
            "label": "Web App",
            "icon": "▣",
            "status": "online",
            "value": "SPA",
            "detail": "Dashboard web servido pelo FastAPI.",
            "target_view": "overview",
        },
        {
            "id": "voice",
            "group": "interfaces",
            "label": "DevPilVoz",
            "icon": "◉",
            "status": "online",
            "value": "Voz",
            "detail": "Entrada por voz com transcrição, fallback e auditoria.",
            "target_view": "voice-admin",
        },
        {
            "id": "api",
            "group": "entry",
            "label": "FastAPI",
            "icon": "⇄",
            "status": "online",
            "value": "API",
            "detail": "Ponto central de entrada, roteamento e políticas de acesso.",
            "target_view": None,
        },
        {
            "id": "auth",
            "group": "core",
            "label": "Autenticação / RBAC",
            "icon": "◆",
            "status": "online",
            "value": f"{users_active}/{users_total}",
            "detail": f"{users_active} usuário(s) ativo(s) de {users_total}; SUPER_ADMIN possui visão global.",
            "target_view": None,
        },
        {
            "id": "projects",
            "group": "core",
            "label": "Projetos",
            "icon": "◇",
            "status": "online" if projects_total else "idle",
            "value": projects_total,
            "detail": f"{projects_total} projeto(s) conectado(s) ao workspace.",
            "target_view": "projects",
        },
        {
            "id": "tasks",
            "group": "core",
            "label": "Desenvolvimento",
            "icon": "⚙",
            "status": "warn" if tasks_failed else "online" if tasks_active else "idle",
            "value": tasks_active,
            "detail": f"{tasks_total} tarefa(s) no total; {tasks_active} ativa(s); {tasks_failed} falha(s).",
            "target_view": "tasks",
        },
        {
            "id": "worker",
            "group": "core",
            "label": "Worker / Execução",
            "icon": "▶",
            "status": "online" if worker_enabled else "idle",
            "value": runs_active,
            "detail": worker_detail,
            "target_view": "tasks",
        },
        {
            "id": "database",
            "group": "data",
            "label": "Banco de Dados",
            "icon": "▤",
            "status": "online",
            "value": db_backend,
            "detail": f"Persistência ativa via {db_backend}; credenciais não são expostas neste painel.",
            "target_view": None,
        },
        {
            "id": "audit",
            "group": "data",
            "label": "Auditoria",
            "icon": "✓",
            "status": "warn" if audit_failed_24h else "online",
            "value": audit_24h,
            "detail": f"{audit_24h} evento(s) nas últimas 24h; {audit_failed_24h} falha(s).",
            "target_view": "audit",
        },
        {
            "id": "github",
            "group": "external",
            "label": "GitHub",
            "icon": "⌘",
            "status": "warn" if organization_errors else "online" if organizations_total else "idle",
            "value": repositories_total,
            "detail": f"{organizations_total} organização(ões), {repositories_total} repositório(s), {organization_errors} erro(s) de sincronização.",
            "target_view": "organizations",
        },
        {
            "id": "providers",
            "group": "external",
            "label": "Modelos de IA",
            "icon": "✦",
            "status": "online" if providers_enabled else "warn",
            "value": len(providers_enabled),
            "detail": "Ativos: " + (", ".join(provider_names) if provider_names else "nenhum provedor configurado"),
            "target_view": "providers",
        },
        {
            "id": "linux",
            "group": "external",
            "label": "Agente Linux",
            "icon": ">_",
            "status": "configured" if settings.linux_agent_url else "idle",
            "value": "host",
            "detail": "Canal configurado para ações no Linux; o painel não presume conectividade sem uma execução comprovada.",
            "target_view": None,
        },
    ]

    edges = [
        {"from": "web", "to": "api", "type": "sync", "label": "HTTPS / API"},
        {"from": "voice", "to": "api", "type": "sync", "label": "áudio / comando"},
        {"from": "api", "to": "auth", "type": "sync", "label": "token / RBAC"},
        {"from": "auth", "to": "projects", "type": "read-write", "label": "escopo"},
        {"from": "projects", "to": "tasks", "type": "read-write", "label": "orquestra"},
        {"from": "tasks", "to": "worker", "type": "async", "label": "fila / execução"},
        {"from": "worker", "to": "github", "type": "sync", "label": "Git / PR"},
        {"from": "worker", "to": "providers", "type": "sync", "label": "inferência"},
        {"from": "worker", "to": "linux", "type": "async", "label": "host actions"},
        {"from": "projects", "to": "database", "type": "read-write", "label": "persistência"},
        {"from": "tasks", "to": "database", "type": "read-write", "label": "estado"},
        {"from": "api", "to": "audit", "type": "async", "label": "eventos"},
        {"from": "worker", "to": "audit", "type": "async", "label": "evidências"},
        {"from": "voice", "to": "providers", "type": "sync", "label": "transcrição"},
    ]

    warnings: list[str] = []
    if not providers_enabled:
        warnings.append("Nenhum provedor de IA ativo foi encontrado.")
    if not worker_enabled:
        warnings.append("Nenhuma execução ativa ou worker habilitado foi comprovado neste instante.")
    if organization_errors:
        warnings.append(f"Há {organization_errors} organização(ões) com erro de sincronização Git.")
    if tasks_failed:
        warnings.append(f"Há {tasks_failed} tarefa(s) em estado failed.")

    return {
        "generated_at": now,
        "summary": {
            "users": users_total,
            "projects": projects_total,
            "active_tasks": tasks_active,
            "repositories": repositories_total,
            "providers": len(providers_enabled),
            "audit_24h": audit_24h,
        },
        "flow": [
            {"order": 1, "label": "Usuário acessa", "detail": "Web ou voz entram no DevPilot."},
            {"order": 2, "label": "API autentica", "detail": "FastAPI valida token, conta e RBAC."},
            {"order": 3, "label": "Serviços executam", "detail": "Projetos e tarefas são orquestrados."},
            {"order": 4, "label": "Dados e integrações", "detail": "Worker usa banco, Git, IA e Linux conforme a tarefa."},
            {"order": 5, "label": "Resultado auditado", "detail": "Estado e evidências retornam ao usuário."},
        ],
        "nodes": nodes,
        "edges": edges,
        "warnings": warnings,
    }


@router.get("")
def voice_admin_dashboard(db: Session = Depends(get_db)):
    """Return a secret-free operational view of the DevPilVoz transcription chain."""
    ws = _workspace(db)
    now = datetime.now(timezone.utc)
    if not ws:
        return {
            "generated_at": now,
            "chain": [],
            "connections": [],
            "last_transcription": None,
            "recent_events": [],
            "usage_24h": [],
            "warnings": ["Workspace padrão ainda não foi criado."],
        }

    credentials = list(
        db.scalars(
            select(ProviderCredential)
            .where(ProviderCredential.workspace_id == ws.id)
            .order_by(ProviderCredential.created_at.desc())
        ).all()
    )
    enabled = [item for item in credentials if item.enabled]
    active_by_provider: dict[str, list[ProviderCredential]] = {}
    for item in enabled:
        active_by_provider.setdefault(item.provider.lower(), []).append(item)

    openai_ready = _has_env("OPENAI_API_KEY") or bool(active_by_provider.get("openai"))
    google_ready = _has_env("GEMINI_API_KEY", "GOOGLE_API_KEY") or bool(active_by_provider.get("google"))

    chain = [
        {
            "order": 1,
            "provider": "openai",
            "label": "OpenAI",
            "role": "principal",
            "model": "gpt-4o-mini-transcribe",
            "configured": openai_ready,
        },
        {
            "order": 2,
            "provider": "google",
            "label": "Gemini / Google",
            "role": "fallback",
            "model": "catálogo Gemini Flash selecionado automaticamente",
            "configured": google_ready,
        },
    ]

    connections = [
        {
            "id": item.id,
            "provider": item.provider,
            "label": item.label,
            "enabled": item.enabled,
            "models": _models(item),
            "created_at": item.created_at,
            "used_by_voice_transcription": item.provider.lower() in {"openai", "google"},
        }
        for item in credentials
    ]

    event_query = (
        select(AuditEvent)
        .where(
            AuditEvent.workspace_id == ws.id,
            AuditEvent.action.in_(("voice.transcribed", "voice.transcription_failed")),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(30)
    )
    events = list(db.scalars(event_query).all())
    latest_success = next((event for event in events if event.action == "voice.transcribed"), None)
    latest_details = _details(latest_success)

    recent_events = []
    for event in events[:12]:
        detail = _details(event)
        recent_events.append(
            {
                "id": event.id,
                "action": event.action,
                "outcome": event.outcome,
                "created_at": event.created_at,
                "provider": detail.get("provider"),
                "model": detail.get("model"),
                "fallback": bool(detail.get("fallback", False)),
                "openai_status": detail.get("openai_status"),
                "google_status": detail.get("google_status"),
            }
        )

    since = now - timedelta(hours=24)
    usage_rows = db.execute(
        select(
            TokenUsage.provider,
            TokenUsage.model,
            func.count(TokenUsage.id),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
        )
        .where(
            TokenUsage.workspace_id == ws.id,
            TokenUsage.operation == "voice.transcription",
            TokenUsage.created_at >= since,
        )
        .group_by(TokenUsage.provider, TokenUsage.model)
        .order_by(func.count(TokenUsage.id).desc())
    ).all()
    usage_24h = [
        {
            "provider": provider,
            "model": model,
            "requests": int(requests or 0),
            "tokens": int(tokens or 0),
        }
        for provider, model, requests, tokens in usage_rows
    ]

    warnings: list[str] = []
    voice_inactive = [
        item for item in enabled
        if item.provider.lower() not in {"openai", "google"}
        and any("whisper" in model.lower() for model in _models(item))
    ]
    if voice_inactive:
        labels = ", ".join(item.label for item in voice_inactive[:4])
        warnings.append(
            f"{labels}: conexão com modelo Whisper está cadastrada, mas a cadeia atual de transcrição usa somente OpenAI → Google."
        )
    if not openai_ready:
        warnings.append("OpenAI principal não possui credencial ativa para transcrição.")
    if not google_ready:
        warnings.append("Google/Gemini fallback não possui credencial ativa.")

    return {
        "generated_at": now,
        "chain": chain,
        "connections": connections,
        "last_transcription": (
            {
                "created_at": latest_success.created_at,
                "provider": latest_details.get("provider"),
                "model": latest_details.get("model"),
                "fallback": bool(latest_details.get("fallback", False)),
            }
            if latest_success
            else None
        ),
        "recent_events": recent_events,
        "usage_24h": usage_24h,
        "warnings": warnings,
    }
