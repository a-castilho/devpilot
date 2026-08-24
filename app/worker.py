import json
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project, Run, Task, TaskStatus
from app.services import executor as executor_service
from app.services.ai_costs import budget_block_reason
from app.services.alternating_flow import execute_task
from app.services.audit import record
from app.services.recovery import AutoRecoveryService
from app.services.runtime_preflight import WorkerRuntimeError, worker_runtime_paths
from app.services.task_flow import (
    ACTION_MARKER,
    CORRECTION_STAGE_MARKER,
    FLOW_MARKER,
    IMPLEMENTATION_STAGE_MARKER,
    VERIFICATION_MARKER,
    VERIFICATION_STAGE_MARKER,
    execution_branch,
    is_analysis_action_task,
    is_analysis_task,
    is_correction_action,
    is_verification_analysis,
)
from app.services.task_images import enable_executor_image_support
from app.services.token_usage import extract_codex_usage, record_usage, task_user_id


enable_executor_image_support(executor_service)

# Backward-compatible name used by tests and older integrations.
_ACTION_MARKER = ACTION_MARKER


def _failure_text(result: dict | None, error: Exception | None) -> str:
    if error is not None:
        return str(error)
    if not isinstance(result, dict):
        return "Execution failed without a structured result"
    return str(result.get("stderr") or result.get("summary") or "Execution failed")


def _self_healing_payload(events: list[dict], final_status: str) -> dict:
    last = events[-1] if events else {}
    steps: list[dict] = []
    for event in events:
        steps.extend(event.get("steps") or [])
    return {
        "status": final_status,
        "category": last.get("category", "unknown"),
        "requires_authorization": bool(last.get("requires_authorization", False)),
        "strategy": last.get("strategy", "none"),
        "message": last.get("message", ""),
        "attempts": len(events),
        "steps": steps,
    }


def _project_model(project: Project) -> str:
    try:
        config = json.loads(project.codex_config or "{}")
    except (TypeError, ValueError):
        return "default"
    return str(config.get("model") or "default")


def _record_result_usage(
    db,
    *,
    project: Project,
    task: Task,
    run: Run,
    result: dict | None,
    execution_attempt: int,
) -> None:
    if not isinstance(result, dict):
        return
    counts = extract_codex_usage(str(result.get("stdout") or ""))
    operation = (
        "task.analysis"
        if str(result.get("mode") or "").startswith("analysis")
        else "task.execution"
    )
    usage = record_usage(
        db,
        workspace_id=task.workspace_id,
        user_id=task_user_id(db, task.id),
        project_id=task.project_id,
        task_id=task.id,
        run_id=run.id,
        provider="openai-codex",
        model=_project_model(project),
        operation=operation,
        counts=counts,
        attempt=execution_attempt,
    )
    if usage:
        result["token_usage"] = {
            "id": usage.id,
            **counts.as_dict(),
        }


def _block_for_budget(db, *, task: Task, run: Run, user_id: str | None, reason: str) -> None:
    now = datetime.now(timezone.utc)
    run.status = "blocked"
    run.summary = reason
    run.logs = json.dumps(
        {
            "mode": "budget-blocked",
            "summary": reason,
            "budget_blocked": True,
            "exit_code": 78,
        },
        ensure_ascii=False,
    )
    run.finished_at = now
    task.status = TaskStatus.blocked
    record(
        db,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        task_id=task.id,
        actor=f"user:{user_id}" if user_id else "worker",
        action="ai.budget.blocked",
        outcome="blocked",
        details={"run_id": run.id, "operation": "task.execution", "reason": reason},
    )
    db.commit()


def _final_task_status(run_status: str, needs_authorization: bool) -> TaskStatus:
    """Map execution outcome to the terminal task state used by the dashboard."""
    if run_status == "success":
        return TaskStatus.completed
    if needs_authorization:
        return TaskStatus.blocked
    return TaskStatus.failed


def _is_analysis_task(task: Task) -> bool:
    """Compatibility wrapper around the shared deterministic flow classifier."""
    return is_analysis_task(task)


def _is_analysis_action_task(task: Task) -> bool:
    return is_analysis_action_task(task)


def _is_correction_action(task: Task) -> bool:
    return is_correction_action(task)


def _analysis_report(result: dict | None, run: Run) -> str:
    payload = result if isinstance(result, dict) else {}
    for key in ("client_report", "summary", "stdout"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value[:100_000]
    return str(run.summary or "Análise concluída sem relatório textual.").strip()[:100_000]


def _analysis_action_priority(report: str) -> int:
    normalized = str(report or "").lower()
    if any(
        signal in normalized
        for signal in ("crítico", "critico", "bloqueio", "segurança", "seguranca", "credencial")
    ):
        return 90
    if any(signal in normalized for signal in ("alto", "importante", "risco")):
        return 80
    return 70


def _analysis_action_title(project: Project, correction: bool = False) -> str:
    if correction:
        return f"Correção pós-validação · {project.name}"[:240]
    return f"Ação recomendada · {project.name}"[:240]


def _analysis_action_prompt(
    run: Run,
    report: str,
    *,
    correction: bool = False,
    target_branch: str = "",
) -> str:
    marker = f"[analysis-run:{run.id}]"
    stage = CORRECTION_STAGE_MARKER if correction else IMPLEMENTATION_STAGE_MARKER
    branch_marker = f"[execution-branch:{target_branch}]\n" if target_branch else ""
    instruction = (
        "Execute somente as correções residuais apontadas pela validação abaixo. "
        "Esta é a correção final do ciclo: não crie uma nova análise depois dela. "
        if correction
        else "Execute as correções e melhorias recomendadas no diagnóstico abaixo. "
        "Não faça uma nova análise nesta etapa: transforme os achados em implementação verificável. "
    )
    return (
        f"{FLOW_MARKER}\n"
        f"{stage}\n"
        "[DEVPILOT_MODE=fix]\n"
        f"{ACTION_MARKER}\n"
        f"{marker}\n"
        f"{branch_marker}"
        f"{instruction}"
        "Priorize riscos críticos, preserve compatibilidade, execute testes relevantes e "
        "registre claramente o que foi alterado.\n\n"
        "DIAGNÓSTICO DE ORIGEM:\n"
        f"{report}"
    )[:100_000]


def _verification_analysis_title(project: Project) -> str:
    return f"Validação pós-execução · {project.name}"[:240]


def _verification_analysis_prompt(run: Run, task: Task, branch: str) -> str:
    return (
        f"{FLOW_MARKER}\n"
        f"{VERIFICATION_STAGE_MARKER}\n"
        "[DEVPILOT_MODE=analysis-read-only]\n"
        f"{VERIFICATION_MARKER}\n"
        f"[execution-task:{task.id}]\n"
        f"[execution-run:{run.id}]\n"
        f"[execution-branch:{branch}]\n"
        "Valide a implementação que acabou de ser executada. Analise exatamente o snapshot da branch "
        "de execução, confirme com evidências o que foi corrigido, identifique regressões e liste somente "
        "lacunas residuais que ainda exigem correção. Não modifique arquivos nesta etapa."
    )[:100_000]


def _ensure_analysis_action(
    db,
    *,
    project: Project,
    task: Task,
    run: Run,
    result: dict | None,
) -> Task | None:
    if run.status != "success" or not _is_analysis_task(task):
        return None
    if not str((result or {}).get("mode") or "").startswith("analysis-read-only"):
        return None

    marker = f"[analysis-run:{run.id}]"
    existing = db.scalar(
        select(Task)
        .where(
            Task.workspace_id == task.workspace_id,
            Task.project_id == task.project_id,
            Task.prompt.contains(marker),
        )
        .limit(1)
    )
    if existing:
        return existing

    report = _analysis_report(result, run)
    correction = is_verification_analysis(task)
    target_branch = execution_branch(task) if correction else ""
    action_task = Task(
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        title=_analysis_action_title(project, correction=correction),
        prompt=_analysis_action_prompt(
            run,
            report,
            correction=correction,
            target_branch=target_branch,
        ),
        source="analysis-action",
        status=TaskStatus.queued,
        requires_approval=False,
        priority=100,
    )
    db.add(action_task)
    db.flush()
    record(
        db,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        task_id=action_task.id,
        actor="worker",
        action="analysis.action_created",
        outcome="queued",
        details={
            "analysis_task_id": task.id,
            "analysis_run_id": run.id,
            "priority": action_task.priority,
            "automatic": True,
            "flow_stage": "correct" if correction else "execute",
            "target_branch": target_branch,
        },
    )
    return action_task


def _ensure_execution_verification(
    db,
    *,
    project: Project,
    task: Task,
    run: Run,
    result: dict | None,
) -> Task | None:
    if run.status != "success" or not _is_analysis_action_task(task):
        return None
    if _is_correction_action(task):
        return None
    if str((result or {}).get("mode") or "") != "execute":
        return None

    branch = str((result or {}).get("branch") or "").strip()
    if not branch:
        return None

    marker = f"[execution-run:{run.id}]"
    existing = db.scalar(
        select(Task)
        .where(
            Task.workspace_id == task.workspace_id,
            Task.project_id == task.project_id,
            Task.prompt.contains(marker),
        )
        .limit(1)
    )
    if existing:
        return existing

    verification = Task(
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        title=_verification_analysis_title(project),
        prompt=_verification_analysis_prompt(run, task, branch),
        source="execution-verification",
        status=TaskStatus.queued,
        requires_approval=False,
        priority=100,
    )
    db.add(verification)
    db.flush()
    record(
        db,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        task_id=verification.id,
        actor="worker",
        action="analysis.verification_created",
        outcome="queued",
        details={
            "execution_task_id": task.id,
            "execution_run_id": run.id,
            "branch": branch,
            "automatic": True,
            "flow_stage": "verify",
        },
    )
    return verification


def process_one() -> bool:
    with SessionLocal() as db:
        task = db.scalar(
            select(Task)
            .where(Task.status == TaskStatus.queued)
            .order_by(Task.priority.desc(), Task.created_at)
            .limit(1)
        )
        if not task:
            return False
        project = db.get(Project, task.project_id)
        task.status = TaskStatus.running
        run = Run(task_id=task.id)
        db.add(run)
        db.commit()

        owner_user_id = task_user_id(db, task.id)
        budget_reason = budget_block_reason(
            db,
            workspace_id=task.workspace_id,
            user_id=owner_user_id,
            project_id=task.project_id,
        )
        if budget_reason:
            _block_for_budget(
                db,
                task=task,
                run=run,
                user_id=owner_user_id,
                reason=budget_reason,
            )
            return True

        recovery = AutoRecoveryService()
        recovery_events: list[dict] = []
        result: dict | None = None
        final_error: Exception | None = None

        for execution_attempt in range(1, recovery.MAX_ATTEMPTS + 1):
            budget_reason = budget_block_reason(
                db,
                workspace_id=task.workspace_id,
                user_id=owner_user_id,
                project_id=task.project_id,
            )
            if budget_reason:
                _block_for_budget(
                    db,
                    task=task,
                    run=run,
                    user_id=owner_user_id,
                    reason=budget_reason,
                )
                return True

            run.attempt = execution_attempt
            current_error: Exception | None = None
            try:
                result = execute_task(project, task)
            except Exception as error:
                current_error = error
                result = None

            _record_result_usage(
                db,
                project=project,
                task=task,
                run=run,
                result=result,
                execution_attempt=execution_attempt,
            )

            succeeded = isinstance(result, dict) and result.get("exit_code", 0) == 0
            if succeeded:
                final_error = None
                if recovery_events:
                    result["self_healing"] = _self_healing_payload(recovery_events, "resolved")
                    result["summary"] = (
                        "Autocorreção concluída e tarefa retomada automaticamente. "
                        + str(result.get("summary") or "Execução concluída.")
                    )
                break

            failure_text = _failure_text(result, current_error)
            decision = recovery.recover(project, task, failure_text, execution_attempt)
            recovery_events.append(decision.to_dict())
            final_error = current_error

            if decision.retry and execution_attempt < recovery.MAX_ATTEMPTS:
                record(
                    db,
                    workspace_id=task.workspace_id,
                    project_id=task.project_id,
                    task_id=task.id,
                    actor="worker",
                    action="task.self_healing.retry",
                    outcome="retrying",
                    details={
                        "run_id": run.id,
                        "execution_attempt": execution_attempt,
                        "category": decision.category,
                        "strategy": decision.strategy,
                    },
                )
                db.commit()
                continue

            if result is None:
                result = recovery.failure_result(decision, failure_text)
            else:
                result["self_healing"] = _self_healing_payload(recovery_events, decision.status)
                if decision.requires_authorization or decision.status in {"needs_attention", "needs_authorization"}:
                    result["summary"] = decision.message
            break

        if result is None:
            decision = recovery.recover(
                project,
                task,
                str(final_error or "Execution failed"),
                recovery.MAX_ATTEMPTS,
            )
            recovery_events.append(decision.to_dict())
            result = recovery.failure_result(decision, str(final_error or "Execution failed"))

        run.status = "success" if result.get("exit_code", 0) == 0 else "failed"
        run.summary = result.get("summary", "Execution completed")
        run.logs = json.dumps(result, ensure_ascii=False)

        healing = result.get("self_healing") if isinstance(result, dict) else None
        needs_authorization = bool(isinstance(healing, dict) and healing.get("requires_authorization"))
        task.status = _final_task_status(run.status, needs_authorization)

        if isinstance(healing, dict):
            record(
                db,
                workspace_id=task.workspace_id,
                project_id=task.project_id,
                task_id=task.id,
                actor="worker",
                action="task.self_healing",
                outcome=str(healing.get("status") or "failed"),
                details={
                    "run_id": run.id,
                    "category": healing.get("category", "unknown"),
                    "strategy": healing.get("strategy", "none"),
                    "attempts": run.attempt,
                    "requires_authorization": needs_authorization,
                },
            )

        outcome = run.status
        run.finished_at = datetime.now(timezone.utc)
        generated_action = _ensure_analysis_action(
            db,
            project=project,
            task=task,
            run=run,
            result=result,
        )
        generated_verification = _ensure_execution_verification(
            db,
            project=project,
            task=task,
            run=run,
            result=result,
        )
        record(
            db,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor="worker",
            action="task.executed",
            outcome=outcome,
            details={
                "run_id": run.id,
                "attempt": run.attempt,
                "generated_action_task_id": generated_action.id if generated_action else None,
                "generated_verification_task_id": (
                    generated_verification.id if generated_verification else None
                ),
            },
        )
        db.commit()
        return True


def main() -> None:
    try:
        runtime = worker_runtime_paths()
    except WorkerRuntimeError as error:
        print(f"[worker] PRECHECK FAILED: {error}", flush=True)
        raise SystemExit(78) from error

    print(
        "[worker] runtime OK: "
        + ", ".join(f"{tool}={path}" for tool, path in runtime.items()),
        flush=True,
    )

    while True:
        if not process_one():
            time.sleep(2)


if __name__ == "__main__":
    main()
