from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project, Run, Task, TaskStatus, Workspace
from app.project_provisioning_routes import (
    provision_repository_and_resume_task,
    queue_repository_repair,
    repository_provision_state,
)
from app.security import require_access
from app.services.audit import record
from app.services.failure_recovery import (
    apply_user_guidance,
    enrich_failure_from_run,
    ensure_failure_recovery_task,
    find_failure_recovery_task,
    latest_run_for_task,
    resume_original_after_recovery,
)
from app.task_run_routes import failure_details, sanitize_payload


router = APIRouter(prefix="/api", dependencies=[Depends(require_access)])

_STDIN_FAILURE_MARKERS = (
    "reading additional input from stdin",
    "failed to read prompt from stdin",
    "no prompt provided via stdin",
)


class RecoveryGuidance(BaseModel):
    instruction: str = Field(min_length=3, max_length=4000)


def _workspace_id(db: Session) -> str:
    workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == "default"))
    if not workspace_id:
        raise HTTPException(404, "Workspace not found")
    return workspace_id


def _task(db: Session, task_id: str) -> Task:
    workspace_id = _workspace_id(db)
    task = db.scalar(select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id))
    if not task:
        raise HTTPException(404, "Task not found")
    return task


def _healing_payload(run: Run | None) -> dict:
    if not run or not run.logs:
        return {}
    try:
        payload = json.loads(run.logs)
    except (TypeError, ValueError):
        return {}
    healing = payload.get("self_healing") if isinstance(payload, dict) else None
    return sanitize_payload(healing) if isinstance(healing, dict) else {}


def _status_value(value) -> str:
    return value.value if isinstance(value, TaskStatus) else str(value or "")


def _recovery_state(original: Task, recovery: Task | None) -> str:
    original_status = _status_value(original.status)
    if original_status == TaskStatus.completed.value:
        return "resolved"
    if original_status in {
        TaskStatus.queued.value,
        TaskStatus.planning.value,
        TaskStatus.running.value,
        TaskStatus.review.value,
    }:
        return "retesting"
    if recovery is None:
        return "ready_to_recover"

    recovery_status = _status_value(recovery.status)
    if recovery_status == TaskStatus.awaiting_approval.value:
        return "awaiting_intervention" if recovery.requires_approval else "ready_to_recover"
    if recovery_status in {
        TaskStatus.queued.value,
        TaskStatus.planning.value,
        TaskStatus.running.value,
        TaskStatus.review.value,
    }:
        return "agent_recovery"
    if recovery_status in {TaskStatus.failed.value, TaskStatus.blocked.value}:
        return "intervention_required"
    if recovery_status == TaskStatus.completed.value and original_status in {
        TaskStatus.failed.value,
        TaskStatus.blocked.value,
    }:
        return "recovery_exhausted"
    return "ready_to_recover"


def _authorization_error(value: str) -> bool:
    text = str(value or "").casefold()
    return any(
        marker in text
        for marker in (
            "credencial",
            "credential",
            "token",
            "unauthorized",
            "forbidden",
            "401",
            "403",
            "permission",
            "permissão",
            "autoriz",
        )
    )


def _platform_failure(failure: dict | None) -> dict:
    """Reclassify known DevPilot runner faults even for historical failed runs.

    Older runs persisted the Codex non-TTY stdin hang as ``unknown`` and therefore
    generated a project-repair task. That repair can never fix the real cause because
    the defect lives in the DevPilot worker process. Keep the original technical
    evidence, but expose the actual platform category and the exact safe action.
    """
    result = dict(failure or {})
    technical = str(
        result.get("technical_message")
        or result.get("message")
        or ""
    ).strip()
    normalized = technical.casefold()
    if not any(marker in normalized for marker in _STDIN_FAILURE_MARKERS):
        return result

    result.update(
        {
            "category": "executor_runtime",
            "code": "EXECUTOR_STDIN_BLOCKED",
            "message": (
                "O runner do DevPilot iniciou o Codex em ambiente não interativo e o CLI aguardou "
                "entrada adicional pelo stdin antes de executar o prompt."
            ),
            "technical_message": technical[:2400],
            "requires_authorization": False,
            "recommended_action": (
                "Reexecutar exatamente esta tarefa no runner DevPilot corrigido, com stdin não interativo "
                "isolado/encerrado. Não alterar o projeto e não criar uma tarefa de reparo do repositório."
            ),
        }
    )
    return result


def _repository_failure(project: Project, fallback: dict) -> tuple[dict, dict, str, bool]:
    provision = repository_provision_state(project)
    provider_error = str(provision.get("error") or "").strip()
    fallback_reason = str(
        fallback.get("technical_message")
        or fallback.get("message")
        or ""
    ).strip()
    technical = provider_error or fallback_reason or (
        "O projeto ainda não possui repository_url. A execução não pode abrir um checkout Git válido."
    )
    requires_authorization = _authorization_error(provider_error)

    if provider_error and requires_authorization:
        correction = (
            "Corrigir a credencial/autorização GitHub indicada pelo diagnóstico e reprovisionar o "
            "repositório do projeto. A etapa original só será retomada depois que repository_url existir."
        )
    elif provision.get("state") in {"queued", "pending"}:
        correction = (
            "Concluir o provisionamento do repositório GitHub e retomar automaticamente esta mesma "
            "etapa quando repository_url estiver preenchido."
        )
    else:
        correction = (
            "Reprovisionar o repositório GitHub do projeto e, somente após obter um clone_url válido, "
            "reenfileirar exatamente esta etapa."
        )

    failure = {
        "category": "repository_not_ready",
        "code": "REPOSITORY_NOT_READY",
        "message": technical[:2400],
        "technical_message": technical[:2400],
        "requires_authorization": requires_authorization,
        "recommended_action": correction[:2400],
    }

    state_value = str(provision.get("state") or "pending")
    if state_value in {"queued", "pending"}:
        state = "agent_recovery"
    elif requires_authorization:
        state = "awaiting_intervention"
    else:
        state = "ready_to_recover"
    return failure, provision, state, requires_authorization


def _repository_payload(db: Session, original: Task, project: Project, original_run: Run | None) -> dict:
    fallback = enrich_failure_from_run(original_run, failure_details(original_run))
    failure, provision, state, manual = _repository_failure(project, fallback)
    return {
        "task_id": original.id,
        "task_title": original.title,
        "task_status": _status_value(original.status),
        "state": state,
        "manual_intervention_required": manual,
        "can_resume_original": False,
        "failure": failure,
        "self_healing": _healing_payload(original_run),
        "original_run": {
            "id": original_run.id if original_run else None,
            "attempt": original_run.attempt if original_run else 0,
            "status": original_run.status if original_run else None,
        },
        # Uma recovery task antiga que também falhou por falta de checkout não é
        # autoridade de reparo para esta causa. O reparo correto é o provisionamento.
        "recovery_task": None,
        "repository_provisioning": provision,
    }


def _platform_payload(original: Task, original_run: Run | None, failure: dict) -> dict:
    original_status = _status_value(original.status)
    if original_status == TaskStatus.completed.value:
        state = "resolved"
    elif original_status in {
        TaskStatus.queued.value,
        TaskStatus.planning.value,
        TaskStatus.running.value,
        TaskStatus.review.value,
    }:
        state = "retesting"
    else:
        state = "ready_to_recover"

    return {
        "task_id": original.id,
        "task_title": original.title,
        "task_status": original_status,
        "state": state,
        "manual_intervention_required": False,
        "can_resume_original": False,
        "failure": failure,
        "self_healing": _healing_payload(original_run),
        "original_run": {
            "id": original_run.id if original_run else None,
            "attempt": original_run.attempt if original_run else 0,
            "status": original_run.status if original_run else None,
        },
        # Falha interna do runner: uma recovery task de projeto é conceitualmente
        # errada e pode falhar pelo mesmo executor. O clique reenfileira a origem.
        "recovery_task": None,
        "platform_recovery": {
            "kind": "executor_runtime",
            "action": "requeue_original",
            "explicit_user_trigger": True,
        },
    }


def _payload(db: Session, original: Task) -> dict:
    original_run = latest_run_for_task(db, original.id)
    project = db.get(Project, original.project_id)
    if project and not str(project.repository_url or "").strip():
        return _repository_payload(db, original, project, original_run)

    original_failure = _platform_failure(
        enrich_failure_from_run(original_run, failure_details(original_run))
    )
    if original_failure.get("category") == "executor_runtime":
        return _platform_payload(original, original_run, original_failure)

    recovery = find_failure_recovery_task(db, original)
    recovery_run = latest_run_for_task(db, recovery.id) if recovery else None
    recovery_failure = _platform_failure(
        enrich_failure_from_run(
            recovery_run,
            failure_details(recovery_run) if recovery_run else {
                "category": "",
                "code": "",
                "message": "",
                "requires_authorization": False,
            },
        )
    )
    state = _recovery_state(original, recovery)

    # Recuperações antigas podem já ter terminado em failed antes do contrato V97.
    # Se não há evidência de autorização/credencial pendente, exponha novamente o
    # botão de correção em vez de transformar um erro técnico seguro em bloqueio manual.
    if (
        state in {"intervention_required", "recovery_exhausted"}
        and recovery
        and not recovery.requires_approval
        and not bool(recovery_failure.get("requires_authorization"))
    ):
        state = "ready_to_recover"

    manual = state in {
        "awaiting_intervention",
        "intervention_required",
        "recovery_exhausted",
    }
    can_resume = bool(
        recovery
        and recovery.status == TaskStatus.completed
        and recovery_run
        and recovery_run.status == "success"
        and original.status in {TaskStatus.failed, TaskStatus.blocked}
    )
    return {
        "task_id": original.id,
        "task_title": original.title,
        "task_status": _status_value(original.status),
        "state": state,
        "manual_intervention_required": manual,
        "can_resume_original": can_resume,
        "failure": original_failure,
        "self_healing": _healing_payload(original_run),
        "original_run": {
            "id": original_run.id if original_run else None,
            "attempt": original_run.attempt if original_run else 0,
            "status": original_run.status if original_run else None,
        },
        "recovery_task": {
            "id": recovery.id,
            "title": recovery.title,
            "status": _status_value(recovery.status),
            "requires_approval": bool(recovery.requires_approval),
            "failure": recovery_failure,
            "run_id": recovery_run.id if recovery_run else None,
            "run_status": recovery_run.status if recovery_run else None,
        } if recovery else None,
    }


def _requeue_platform_failure(db: Session, original: Task, run: Run | None, failure: dict) -> None:
    previous_status = _status_value(original.status)
    original.status = TaskStatus.queued
    original.updated_at = datetime.now(timezone.utc)
    record(
        db,
        workspace_id=original.workspace_id,
        project_id=original.project_id,
        task_id=original.id,
        actor="owner",
        action="failure_recovery.platform_runner_requeued",
        outcome="queued",
        details={
            "previous_status": previous_status,
            "run_id": run.id if run else None,
            "failure_code": failure.get("code"),
            "failure_category": failure.get("category"),
            "reason": "explicit_fix_and_continue_after_runner_fix",
        },
    )


@router.get("/tasks/{task_id}/recovery")
def recovery_status(task_id: str, db: Session = Depends(get_db)):
    return _payload(db, _task(db, task_id))


@router.post("/tasks/{task_id}/recovery/escalate")
def escalate_recovery(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    original = _task(db, task_id)
    if original.status not in {TaskStatus.failed, TaskStatus.blocked}:
        raise HTTPException(409, "Only failed or blocked tasks can enter recovery")

    project = db.get(Project, original.project_id)
    if project and not str(project.repository_url or "").strip():
        current = _repository_payload(db, original, project, latest_run_for_task(db, original.id))
        if current["failure"].get("requires_authorization"):
            return current
        queue_repository_repair(db, project, actor="owner", task_id=original.id)
        db.commit()
        background_tasks.add_task(
            provision_repository_and_resume_task,
            project.id,
            original.workspace_id,
            original.id,
            "owner",
        )
        return _payload(db, original)

    run = latest_run_for_task(db, original.id)
    failure = _platform_failure(enrich_failure_from_run(run, failure_details(run)))
    if failure.get("category") == "executor_runtime":
        _requeue_platform_failure(db, original, run, failure)
        db.commit()
        return _payload(db, original)

    recovery = ensure_failure_recovery_task(
        db,
        original_task=original,
        run=run,
        failure=failure,
        actor="owner",
    )
    if not recovery:
        raise HTTPException(409, "Recovery flow is not available for this task")
    db.commit()
    return _payload(db, original)


@router.post("/tasks/{task_id}/recovery/intervene")
def intervene_recovery(
    task_id: str,
    payload: RecoveryGuidance,
    db: Session = Depends(get_db),
):
    original = _task(db, task_id)
    recovery = find_failure_recovery_task(db, original)
    if not recovery:
        run = latest_run_for_task(db, original.id)
        recovery = ensure_failure_recovery_task(
            db,
            original_task=original,
            run=run,
            failure=enrich_failure_from_run(run, failure_details(run)),
            actor="owner",
        )
        if not recovery:
            raise HTTPException(409, "Recovery flow is not available for this task")
    try:
        apply_user_guidance(
            db,
            original_task=original,
            instruction=payload.instruction,
            actor="owner",
        )
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    db.commit()
    return _payload(db, original)


@router.post("/tasks/{task_id}/recovery/resume")
def resume_original(task_id: str, db: Session = Depends(get_db)):
    original = _task(db, task_id)
    recovery = find_failure_recovery_task(db, original)
    if not recovery:
        raise HTTPException(409, "Recovery task not found")
    recovery_run = latest_run_for_task(db, recovery.id)
    if recovery.status != TaskStatus.completed or not recovery_run or recovery_run.status != "success":
        raise HTTPException(409, "Recovery must complete successfully before retesting the original task")
    resumed = resume_original_after_recovery(
        db,
        recovery_task=recovery,
        recovery_run=recovery_run,
    )
    if not resumed:
        raise HTTPException(409, "Original task cannot be resumed")
    db.commit()
    return _payload(db, original)
