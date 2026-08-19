from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.errors import CommandExecutionError
from app.agentos.application.ports import (
    AgentCommand,
    CommandResult,
    ExecutionRecord,
    GoalRecord,
    LanguageModelPort,
    StepExecutionRecord,
)
from app.agentos.models import AgentExecution, AgentStepExecution
from app.models import Run, Task, TaskStatus


def now() -> datetime:
    return datetime.now(timezone.utc)


def load_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


class SQLAlchemyExecutionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _execution(item: AgentExecution) -> ExecutionRecord:
        return ExecutionRecord(
            id=item.id,
            goal_id=item.goal_id,
            workspace_id=item.workspace_id,
            project_id=item.project_id,
            status=item.status,
            idempotency_key=item.idempotency_key,
            current_step_id=item.current_step_id,
            failure_reason=item.failure_reason,
            checkpoint=load_json(item.checkpoint_json, {}),
            started_at=item.started_at,
            completed_at=item.completed_at,
        )

    @staticmethod
    def _step(item: AgentStepExecution) -> StepExecutionRecord:
        return StepExecutionRecord(
            id=item.id,
            execution_id=item.execution_id,
            step_id=item.step_id,
            agent=item.agent,
            title=item.title,
            objective=item.objective,
            depends_on=load_json(item.depends_on_json, []),
            tools=load_json(item.tools_json, []),
            approval_required=bool(item.approval_required),
            approved_at=item.approved_at,
            status=item.status,
            attempt=item.attempt,
            max_attempts=item.max_attempts,
            idempotency_key=item.idempotency_key,
            command=load_json(item.command_json, {}),
            output=load_json(item.output_json, {}),
            checkpoint=load_json(item.checkpoint_json, {}),
            external_task_id=item.external_task_id,
            error=item.error,
            next_attempt_at=item.next_attempt_at,
        )

    def create(self, *, goal: GoalRecord, idempotency_key: str,
               max_attempts: int) -> ExecutionRecord:
        execution = AgentExecution(
            goal_id=goal.id,
            workspace_id=goal.workspace_id,
            project_id=goal.project_id,
            status="pending",
            idempotency_key=idempotency_key,
        )
        self.db.add(execution)
        self.db.flush()
        for position, step in enumerate(goal.plan.steps):
            item = AgentStepExecution(
                execution_id=execution.id,
                step_id=step.id,
                agent=step.agent,
                title=step.title,
                objective=step.objective,
                depends_on_json=json.dumps(step.depends_on),
                tools_json=json.dumps(step.tools),
                approval_required=1 if step.approval_required else 0,
                status="pending",
                max_attempts=max_attempts,
                idempotency_key=f"{execution.id}:{position}:{step.id}",
            )
            self.db.add(item)
        self.db.flush()
        return self._execution(execution)

    def get_by_idempotency(self, *, workspace_id: str,
                           idempotency_key: str) -> ExecutionRecord | None:
        item = self.db.scalar(select(AgentExecution).where(
            AgentExecution.workspace_id == workspace_id,
            AgentExecution.idempotency_key == idempotency_key,
        ))
        return self._execution(item) if item else None

    def get(self, *, workspace_id: str, execution_id: str) -> ExecutionRecord | None:
        item = self.db.scalar(select(AgentExecution).where(
            AgentExecution.id == execution_id,
            AgentExecution.workspace_id == workspace_id,
        ))
        return self._execution(item) if item else None

    def next_active(self) -> ExecutionRecord | None:
        item = self.db.scalar(
            select(AgentExecution)
            .where(AgentExecution.status.in_(["pending", "running"]))
            .order_by(AgentExecution.started_at)
            .limit(1)
        )
        return self._execution(item) if item else None

    def steps(self, *, execution_id: str) -> list[StepExecutionRecord]:
        items = self.db.scalars(
            select(AgentStepExecution)
            .where(AgentStepExecution.execution_id == execution_id)
            .order_by(AgentStepExecution.id)
        ).all()
        return [self._step(item) for item in items]

    def set_execution(self, *, execution_id: str, status: str | None = None,
                      current_step_id: str | None = None,
                      failure_reason: str | None = None,
                      checkpoint: dict[str, Any] | None = None,
                      completed: bool = False) -> ExecutionRecord:
        item = self.db.get(AgentExecution, execution_id)
        if not item:
            raise CommandExecutionError("Execution not found")
        if status is not None:
            item.status = str(status)
        if current_step_id is not None:
            item.current_step_id = current_step_id
        if failure_reason is not None:
            item.failure_reason = failure_reason
        if checkpoint is not None:
            item.checkpoint_json = json.dumps(checkpoint, default=str)
        item.completed_at = now() if completed else None
        self.db.flush()
        return self._execution(item)

    def set_step(self, *, step_record_id: str, status: str | None = None,
                 attempt: int | None = None, approved: bool = False,
                 command: dict[str, Any] | None = None,
                 output: dict[str, Any] | None = None,
                 checkpoint: dict[str, Any] | None = None,
                 external_task_id: str | None = None,
                 error: str | None = None,
                 next_attempt_at: datetime | None = None,
                 clear_next_attempt: bool = False,
                 started: bool = False, finished: bool = False) -> StepExecutionRecord:
        item = self.db.get(AgentStepExecution, step_record_id)
        if not item:
            raise CommandExecutionError("Execution step not found")
        if status is not None:
            item.status = str(status)
        if attempt is not None:
            item.attempt = attempt
        if approved:
            item.approved_at = now()
        if command is not None:
            item.command_json = json.dumps(command, default=str)
        if output is not None:
            item.output_json = json.dumps(output, default=str)
        if checkpoint is not None:
            item.checkpoint_json = json.dumps(checkpoint, default=str)
        if external_task_id is not None:
            item.external_task_id = external_task_id
        if error is not None:
            item.error = error
        if clear_next_attempt:
            item.next_attempt_at = None
        elif next_attempt_at is not None:
            item.next_attempt_at = next_attempt_at
        if started and item.started_at is None:
            item.started_at = now()
        if finished:
            item.finished_at = now()
        self.db.flush()
        return self._step(item)


class CompositeCommandRunner:
    def __init__(self, db: Session, model: LanguageModelPort) -> None:
        self.db = db
        self.model = model

    def run(self, command: AgentCommand, step: StepExecutionRecord) -> CommandResult:
        if command.kind == "devpilot_task":
            return self._delegate_task(command, step)
        if command.kind == "llm":
            return self._run_llm(command, step)
        raise CommandExecutionError(f"Unsupported command kind: {command.kind}")

    def poll(self, command: AgentCommand, step: StepExecutionRecord) -> CommandResult:
        if command.kind != "devpilot_task":
            raise CommandExecutionError("Only delegated tasks support polling")
        if not step.external_task_id:
            raise CommandExecutionError("Delegated step has no task checkpoint")
        task = self.db.get(Task, step.external_task_id)
        if not task:
            raise CommandExecutionError("Delegated DevPilot task not found")
        run = self.db.scalar(
            select(Run).where(Run.task_id == task.id).order_by(Run.started_at.desc()).limit(1)
        )
        if task.status == TaskStatus.failed or (run and run.status == "failed"):
            raise CommandExecutionError(run.summary if run else "Delegated task failed")
        if run and run.status == "success":
            return CommandResult(
                status="completed",
                external_task_id=task.id,
                output={
                    "task_id": task.id,
                    "run_id": run.id,
                    "summary": run.summary,
                    "task_status": str(task.status),
                    "branch": task.branch_name,
                },
                checkpoint={"delegated_task_id": task.id, "run_id": run.id},
            )
        return CommandResult(
            status="waiting", external_task_id=task.id,
            checkpoint={"delegated_task_id": task.id, "task_status": str(task.status)},
        )

    def compensate(self, command: AgentCommand, step: StepExecutionRecord) -> dict[str, Any]:
        if command.kind != "devpilot_task" or not step.external_task_id:
            return {"action": "no_side_effect_to_compensate"}
        task = self.db.get(Task, step.external_task_id)
        if not task:
            return {"action": "task_already_absent"}
        if task.status in {TaskStatus.queued, TaskStatus.awaiting_approval}:
            task.status = TaskStatus.blocked
            return {"action": "blocked_pending_task", "task_id": task.id}
        return {
            "action": "preserved_isolated_work",
            "task_id": task.id,
            "task_status": str(task.status),
        }

    def _run_llm(self, command: AgentCommand, step: StepExecutionRecord) -> CommandResult:
        dependencies = command.context.get("dependencies", {})
        context = json.dumps(dependencies, ensure_ascii=False, default=str)[:40_000]
        result = self.model.chat([
            {
                "role": "system",
                "content": (
                    f"You are the AgentOS {command.agent} agent. Work only on the requested "
                    "step. Be concrete, concise and preserve the stated architecture and safety constraints."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Step: {command.title}\nObjective: {command.objective}\n"
                    f"Declared tools: {', '.join(command.tools) or 'none'}\n"
                    f"Dependency outputs:\n{context or '{}'}"
                ),
            },
        ])
        return CommandResult(
            status="completed",
            output={
                "content": result.get("content", ""),
                "provider": result.get("provider", ""),
                "model": result.get("model", ""),
            },
            checkpoint={"attempt": step.attempt, "kind": "llm"},
        )

    def _delegate_task(self, command: AgentCommand,
                       step: StepExecutionRecord) -> CommandResult:
        execution = self.db.get(AgentExecution, step.execution_id)
        if not execution or not execution.project_id:
            raise CommandExecutionError("Repository-writing agent step requires a project")
        task = Task(
            workspace_id=execution.workspace_id,
            project_id=execution.project_id,
            title=f"AgentOS/{command.agent}: {command.title}"[:240],
            prompt=(
                f"Agent role: {command.agent}\n\n{command.objective}\n\n"
                "This task was delegated by AgentOS. Implement only this graph step. "
                "Do not push, merge or deploy. Keep changes on the isolated DevPilot branch.\n\n"
                f"Dependency context: {json.dumps(command.context, ensure_ascii=False, default=str)[:30000]}"
            ),
            source="agentos",
            status=TaskStatus.queued,
            priority=60,
            requires_approval=False,
        )
        self.db.add(task)
        self.db.flush()
        return CommandResult(
            status="waiting",
            external_task_id=task.id,
            checkpoint={"delegated_task_id": task.id, "kind": "devpilot_task"},
        )
