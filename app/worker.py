import json
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Project, Run, Task, TaskStatus
from app.services import executor as executor_service
from app.services.ai_costs import budget_block_reason
from app.services.audit import record
from app.services.mentor_executor import execute_mentor_task
from app.services.recovery import AutoRecoveryService
from app.services.runtime_preflight import WorkerRuntimeError, worker_runtime_paths
from app.services.task_images import enable_executor_image_support
from app.services.token_usage import extract_codex_usage, record_usage, task_user_id


enable_executor_image_support(executor_service)
execute_task = executor_service.execute_task


def _is_read_only_mentor(task: Task) -> bool:
    return task.source == "mentor" and executor_service.is_read_only_task(task)


def execute_queued_task(project: Project, task: Task) -> dict:
    if _is_read_only_mentor(task):
        return execute_mentor_task(project, task)
    return execute_task(project, task)


def _failure_text(result: dict | None, error: Exception | None) -> str:
    if error is not None:
        return str(error)
    if not isinstance(result, dict):
        return "Execution failed without a structured result"
    return str(result.get("stderr") or result.get("summary") or "Execution failed")


def _mentor_failure_result() -> dict:
    return {
        "mode": "analysis-mentor-read-only",
        "exit_code": 1,
        "summary": "A sessão do DevPilot Mentor falhou sem executar autocorreções sobre o ambiente.",
        "client_report": (
            "A sessão de aprendizado não pôde ser concluída. Por segurança, o DevPilot não executou "
            "autocorreção, troca de credenciais ou reparo do checkout durante uma sessão somente leitura."
        ),
        "stderr": "Mentor read-only execution failed",
        "attempted_changes": None,
        "persisted_changes": False,
        "branch": "",
        "agents_md_generated": False,
    }


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
            # Re-check before every self-healing attempt so a retry cannot continue
            # spending after the previous attempt consumed the remaining budget.
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
                result = execute_queued_task(project, task)
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

            if _is_read_only_mentor(task):
                final_error = current_error
                if result is None:
                    result = _mentor_failure_result()
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
        if run.status == "success":
            task.status = TaskStatus.review
        elif needs_authorization:
            task.status = TaskStatus.blocked
        else:
            task.status = TaskStatus.failed

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
        record(
            db,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor="worker",
            action="task.executed",
            outcome=outcome,
            details={"run_id": run.id, "attempt": run.attempt},
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
