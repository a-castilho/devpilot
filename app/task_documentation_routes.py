from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, Run, Task, TaskStatus, Workspace
from app.security import require_access
from app.services.audit import record
from app.services.task_orchestrator import TASK_RUNTIME, TaskOrchestrator, runtime_view
from app.task_run_routes import sanitize_payload, sanitize_text


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])
TaskCommandChannel = Literal["ui", "chat", "voice", "api"]


class TaskCommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=120)
    channel: TaskCommandChannel = "api"


def _workspace_id(db: Session) -> str:
    workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == "default"))
    if not workspace_id:
        raise HTTPException(404, "Workspace not found")
    return workspace_id


def _task_or_404(db: Session, task_id: str) -> Task:
    workspace_id = _workspace_id(db)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id))
    if not task:
        raise HTTPException(404, "Task not found")
    return task


def _orchestrate(db: Session, task_id: str, action: str, actor: str):
    _task_or_404(db, task_id)
    orchestrator = TaskOrchestrator(db, actor=actor)
    try:
        return getattr(orchestrator, action)(task_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from error


def _normalize_command(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(char for char in text if not unicodedata.combining(char)).casefold().split())


def _command_action(value: str) -> str:
    command = _normalize_command(value)
    aliases = {
        "proximo": "next",
        "next": "next",
        "continuar": "next",
        "continuar automaticamente": "auto_advance",
        "automatico": "auto_advance",
        "auto": "auto_advance",
        "parar": "pause",
        "pausar": "pause",
        "pause": "pause",
        "retomar": "resume",
        "resume": "resume",
        "cancelar": "cancel",
        "cancel": "cancel",
        "excluir": "archive",
        "arquivar": "archive",
        "archive": "archive",
    }
    action = aliases.get(command)
    if not action:
        raise HTTPException(422, "Unsupported task command")
    return action


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "task").strip()).strip("-._")
    return (normalized or "task")[:90]


def _run_payload(run: Run) -> dict:
    try:
        raw = json.loads(run.logs or "{}")
    except (TypeError, ValueError):
        raw = {"raw": run.logs or ""}
    payload = sanitize_payload(raw)
    return payload if isinstance(payload, dict) else {"result": payload}


def _run_evidence(run: Run) -> list[str]:
    payload = _run_payload(run)
    evidence: list[str] = []
    for key in ("summary", "client_report"):
        value = sanitize_text(str(payload.get(key) or "")).strip()
        if value and value not in evidence:
            evidence.append(value)
    if run.summary:
        summary = sanitize_text(run.summary).strip()
        if summary and summary not in evidence:
            evidence.append(summary)
    if run.commit_sha:
        evidence.append(f"Commit: `{sanitize_text(run.commit_sha)}`")
    if run.pull_request_url:
        evidence.append(f"Pull request: {sanitize_text(run.pull_request_url)}")
    return evidence


def build_task_documentation(task: Task, project: Project | None, runs: list[Run]) -> str:
    title = sanitize_text(task.title or "Tarefa concluída")
    project_name = sanitize_text(project.name if project else "Projeto indisponível")
    prompt = sanitize_text(task.prompt or "").strip()
    completed_runs = [run for run in runs if str(run.status).lower() == "success"]
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        f"# Implementação concluída — {title}",
        "",
        "> Documento gerado pelo DevPilot a partir do histórico real da tarefa, execuções e evidências registradas.",
        "",
        "## Identificação",
        "",
        f"- Projeto: **{project_name}**",
        f"- Tarefa: `{task.id}`",
        f"- Status: **{task.status.value if isinstance(task.status, TaskStatus) else task.status}**",
        f"- Origem: `{sanitize_text(task.source or '')}`",
        f"- Branch: `{sanitize_text(task.branch_name or '') or 'não registrada'}`",
        f"- Gerado em: `{generated_at}`",
        "",
        "## Objetivo e contexto",
        "",
        prompt or "Contexto original não registrado.",
        "",
        "## Resultado da implementação",
        "",
    ]

    if not runs:
        lines.append("Nenhuma execução foi registrada para esta tarefa.")
    else:
        for index, run in enumerate(runs, start=1):
            started = run.started_at.isoformat() if run.started_at else "não registrado"
            finished = run.finished_at.isoformat() if run.finished_at else "não registrado"
            lines.extend(
                [
                    f"### Execução {index}",
                    "",
                    f"- Run: `{run.id}`",
                    f"- Tentativa: `{run.attempt}`",
                    f"- Status: **{sanitize_text(run.status)}**",
                    f"- Início: `{started}`",
                    f"- Fim: `{finished}`",
                ]
            )
            evidence = _run_evidence(run)
            if evidence:
                lines.extend(["", "**Evidências:**", ""])
                lines.extend(f"- {item}" for item in evidence)
            lines.append("")

    lines.extend(
        [
            "## Validação",
            "",
            (
                f"A tarefa possui **{len(completed_runs)} execução(ões) bem-sucedida(s)** registrada(s). "
                "A conclusão deste documento não substitui os gates técnicos de teste, revisão, CI ou deploy do projeto."
            ),
            "",
            "## Aprendizado para o usuário",
            "",
            "- O histórico acima mostra a sequência real de execução e as evidências usadas para considerar a tarefa concluída.",
            "- Commits, pull requests e relatórios aparecem somente quando foram efetivamente registrados pelo executor.",
            "- Uma nova alteração posterior deve gerar uma nova execução ou tarefa, preservando a rastreabilidade deste fechamento.",
            "",
            "## Próximos passos",
            "",
            "1. Revisar as evidências e confirmar se o resultado atende ao objetivo original.",
            "2. Registrar aprendizado ou observações complementares quando necessário.",
            "3. Avançar para a próxima tarefa/missão do projeto somente pelos controles do orquestrador.",
            "",
        ]
    )
    return "\n".join(lines)


@router.get("/tasks/orchestrator/runtime")
def task_orchestrator_runtime(db: Session = Depends(get_db)):
    workspace_id = _workspace_id(db)
    task_ids = select(Task.id).where(Task.workspace_id == workspace_id)
    rows = db.execute(
        select(TASK_RUNTIME).where(TASK_RUNTIME.c.task_id.in_(task_ids))
    ).mappings().all()
    return {
        "states": {
            str(row["task_id"]): {
                "state": str(row["state"]),
                "auto_advance": bool(row["auto_advance"]),
                "last_action": str(row["last_action"] or ""),
                "last_message": str(row["last_message"] or ""),
            }
            for row in rows
        }
    }


@router.get("/tasks/{task_id}/orchestrator")
def task_orchestrator_state(task_id: str, db: Session = Depends(get_db)):
    task = _task_or_404(db, task_id)
    return runtime_view(db, task)


@router.post("/tasks/{task_id}/command")
def task_command(
    task_id: str,
    payload: TaskCommandRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    action = _command_action(payload.command)
    channel_actor = f"{actor}:{payload.channel}"
    return _orchestrate(db, task_id, action, channel_actor)


@router.post("/tasks/{task_id}/next")
def task_next(
    task_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    return _orchestrate(db, task_id, "next", actor)


@router.post("/tasks/{task_id}/auto")
def task_auto(
    task_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    return _orchestrate(db, task_id, "auto_advance", actor)


@router.post("/tasks/{task_id}/pause")
def task_pause(
    task_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    return _orchestrate(db, task_id, "pause", actor)


@router.post("/tasks/{task_id}/resume")
def task_resume(
    task_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    return _orchestrate(db, task_id, "resume", actor)


@router.post("/tasks/{task_id}/cancel")
def task_cancel(
    task_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    return _orchestrate(db, task_id, "cancel", actor)


@router.post("/tasks/{task_id}/archive")
def task_archive(
    task_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    return _orchestrate(db, task_id, "archive", actor)


@router.post("/tasks/{task_id}/documentation")
def generate_task_documentation(
    task_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_access),
):
    task = _task_or_404(db, task_id)
    if task.status != TaskStatus.completed:
        raise HTTPException(409, "Documentation can only be generated for completed tasks")

    project = db.get(Project, task.project_id)
    runs = db.scalars(
        select(Run).where(Run.task_id == task.id).order_by(Run.started_at, Run.attempt)
    ).all()
    markdown = build_task_documentation(task, project, list(runs))
    filename = f"task-{_safe_filename(task.title)}-{task.id[:8]}.md"

    record(
        db,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        task_id=task.id,
        actor=actor,
        action="task.documentation_generated",
        outcome="success",
        details={"filename": filename, "run_count": len(runs), "format": "markdown"},
    )
    db.commit()

    return {
        "task_id": task.id,
        "filename": filename,
        "format": "markdown",
        "content": markdown,
        "generated_at": datetime.now(timezone.utc),
    }
