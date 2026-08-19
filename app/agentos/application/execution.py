from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from app.agentos.application.errors import CommandExecutionError, ExecutionNotFound
from app.agentos.application.ports import (
    AgentCommand,
    CommandResult,
    CommandRunnerPort,
    EventBusPort,
    ExecutionRecord,
    ExecutionRepositoryPort,
    GoalRepositoryPort,
    StepExecutionRecord,
    ToolPolicyPort,
    UnitOfWorkPort,
)
from app.agentos.domain.events import DomainEvent
from app.agentos.domain.execution import ExecutionStateMachine, ExecutionStatus, StepStatus


def now() -> datetime:
    return datetime.now(timezone.utc)


def build_command(step: StepExecutionRecord, dependencies: dict) -> AgentCommand:
    return AgentCommand(
        kind="devpilot_task" if "repo.write" in step.tools else "llm",
        step_id=step.step_id,
        agent=step.agent,
        title=step.title,
        objective=step.objective,
        tools=step.tools,
        context={"dependencies": dependencies},
    )


def command_payload(command: AgentCommand) -> dict:
    return {
        "kind": command.kind,
        "step_id": command.step_id,
        "agent": command.agent,
        "title": command.title,
        "objective": command.objective,
        "tools": command.tools,
        "context": command.context,
    }


def restore_command(step: StepExecutionRecord) -> AgentCommand:
    data = step.command
    if not data:
        return build_command(step, {})
    return AgentCommand(
        kind=str(data.get("kind", "llm")),
        step_id=step.step_id,
        agent=step.agent,
        title=step.title,
        objective=step.objective,
        tools=[str(item) for item in data.get("tools", step.tools)],
        context=dict(data.get("context", {})),
    )


class GraphExecutionService:
    def __init__(self, *, goals: GoalRepositoryPort, executions: ExecutionRepositoryPort,
                 runner: CommandRunnerPort, events: EventBusPort, uow: UnitOfWorkPort,
                 tool_policy: ToolPolicyPort | None = None) -> None:
        self.goals = goals
        self.executions = executions
        self.runner = runner
        self.events = events
        self.uow = uow
        self.tool_policy = tool_policy

    def start(self, *, workspace_id: str, goal_id: str, idempotency_key: str | None,
              max_attempts: int = 3) -> ExecutionRecord:
        key = idempotency_key or hashlib.sha256(f"{workspace_id}:{goal_id}".encode()).hexdigest()
        existing = self.executions.get_by_idempotency(
            workspace_id=workspace_id, idempotency_key=key
        )
        if existing:
            return existing
        goal = self.goals.get(workspace_id=workspace_id, goal_id=goal_id)
        if not goal:
            raise ExecutionNotFound("Goal not found")
        execution = self.executions.create(goal=goal, idempotency_key=key, max_attempts=max_attempts)
        self.events.publish(DomainEvent(
            name="agentos.execution.started", workspace_id=goal.workspace_id,
            project_id=goal.project_id,
            payload={"execution_id": execution.id, "goal_id": goal.id, "steps": len(goal.plan.steps)},
        ))
        self.uow.commit()
        return execution

    def get(self, *, workspace_id: str, execution_id: str) -> ExecutionRecord | None:
        return self.executions.get(workspace_id=workspace_id, execution_id=execution_id)

    def steps(self, *, execution_id: str) -> list[StepExecutionRecord]:
        return self.executions.steps(execution_id=execution_id)

    def approve_step(self, *, workspace_id: str, execution_id: str,
                     step_id: str) -> StepExecutionRecord:
        execution = self.get(workspace_id=workspace_id, execution_id=execution_id)
        if not execution:
            raise ExecutionNotFound("Execution not found")
        step = next((x for x in self.steps(execution_id=execution_id) if x.step_id == step_id), None)
        if not step:
            raise ExecutionNotFound("Execution step not found")
        if step.status != StepStatus.awaiting_approval:
            raise CommandExecutionError("Step is not awaiting approval")
        ExecutionStateMachine.step(step.status, StepStatus.pending)
        updated = self.executions.set_step(
            step_record_id=step.id, status=StepStatus.pending, approved=True, error=""
        )
        if execution.status == ExecutionStatus.awaiting_approval:
            ExecutionStateMachine.execution(execution.status, ExecutionStatus.running)
            self.executions.set_execution(execution_id=execution.id, status=ExecutionStatus.running)
        self.events.publish(DomainEvent(
            name="agentos.step.approved", workspace_id=execution.workspace_id,
            project_id=execution.project_id,
            payload={"execution_id": execution.id, "step_id": step.step_id},
        ))
        self.uow.commit()
        return updated

    def resume(self, *, workspace_id: str, execution_id: str,
               reset_attempts: bool = False) -> ExecutionRecord:
        execution = self.get(workspace_id=workspace_id, execution_id=execution_id)
        if not execution:
            raise ExecutionNotFound("Execution not found")
        allowed = {ExecutionStatus.failed, ExecutionStatus.compensated, ExecutionStatus.cancelled}
        if execution.status not in allowed:
            raise CommandExecutionError("Execution is not resumable; approval gates must be approved explicitly")
        for step in self.steps(execution_id=execution.id):
            if step.status in {StepStatus.failed, StepStatus.compensated, StepStatus.skipped}:
                ExecutionStateMachine.step(step.status, StepStatus.pending)
                attempt = 0 if reset_attempts else min(step.attempt, max(step.max_attempts - 1, 0))
                self.executions.set_step(
                    step_record_id=step.id, status=StepStatus.pending,
                    attempt=attempt, error="", clear_next_attempt=True,
                )
        ExecutionStateMachine.execution(execution.status, ExecutionStatus.running)
        updated = self.executions.set_execution(
            execution_id=execution.id, status=ExecutionStatus.running,
            failure_reason="", completed=False,
        )
        self.events.publish(DomainEvent(
            name="agentos.execution.resumed", workspace_id=execution.workspace_id,
            project_id=execution.project_id,
            payload={"execution_id": execution.id, "reset_attempts": reset_attempts},
        ))
        self.uow.commit()
        return updated

    def process_one(self) -> bool:
        execution = self.executions.next_active()
        if not execution:
            return False
        if execution.status == ExecutionStatus.pending:
            ExecutionStateMachine.execution(execution.status, ExecutionStatus.running)
            self.executions.set_execution(execution_id=execution.id, status=ExecutionStatus.running)
            self.uow.commit()
            return True
        steps = self.steps(execution_id=execution.id)
        by_id = {step.step_id: step for step in steps}

        waiting = next((s for s in steps if s.status == StepStatus.waiting_external), None)
        if waiting:
            try:
                result = self.runner.poll(restore_command(waiting), waiting)
            except Exception as error:
                self._fail_or_retry(execution, waiting, error)
                self.uow.commit()
                return True
            if result.status == "waiting":
                return False
            self._complete(execution, waiting, result)
            self.uow.commit()
            return True

        due = next((s for s in steps if s.status == StepStatus.retry_wait and
                    (s.next_attempt_at is None or s.next_attempt_at <= now())), None)
        if due:
            ExecutionStateMachine.step(due.status, StepStatus.pending)
            self.executions.set_step(
                step_record_id=due.id, status=StepStatus.pending, clear_next_attempt=True
            )
            self.uow.commit()
            return True

        runnable = next((s for s in steps if s.status == StepStatus.pending and all(
            by_id[d].status == StepStatus.completed for d in s.depends_on if d in by_id
        )), None)
        if not runnable:
            if steps and all(s.status == StepStatus.completed for s in steps):
                ExecutionStateMachine.execution(execution.status, ExecutionStatus.completed)
                self.executions.set_execution(
                    execution_id=execution.id, status=ExecutionStatus.completed,
                    checkpoint={"completed_steps": [s.step_id for s in steps]}, completed=True,
                )
                self.events.publish(DomainEvent(
                    name="agentos.execution.completed", workspace_id=execution.workspace_id,
                    project_id=execution.project_id, payload={"execution_id": execution.id},
                ))
                self.uow.commit()
                return True
            return False

        if runnable.approval_required and runnable.approved_at is None:
            ExecutionStateMachine.step(runnable.status, StepStatus.awaiting_approval)
            self.executions.set_step(step_record_id=runnable.id, status=StepStatus.awaiting_approval)
            ExecutionStateMachine.execution(execution.status, ExecutionStatus.awaiting_approval)
            self.executions.set_execution(
                execution_id=execution.id, status=ExecutionStatus.awaiting_approval,
                current_step_id=runnable.step_id,
            )
            self.events.publish(DomainEvent(
                name="agentos.step.approval_required", workspace_id=execution.workspace_id,
                project_id=execution.project_id,
                payload={"execution_id": execution.id, "step_id": runnable.step_id},
            ))
            self.uow.commit()
            return True

        dependencies = {d: by_id[d].output for d in runnable.depends_on if d in by_id}
        command = build_command(runnable, dependencies)
        ExecutionStateMachine.step(runnable.status, StepStatus.running)
        running = self.executions.set_step(
            step_record_id=runnable.id, status=StepStatus.running,
            attempt=runnable.attempt + 1, command=command_payload(command), error="", started=True,
        )
        self.executions.set_execution(execution_id=execution.id, current_step_id=runnable.step_id)
        self.uow.commit()

        if self.tool_policy is not None:
            try:
                self.tool_policy.assert_allowed(
                    agent=running.agent,
                    tools=running.tools,
                    approval_granted=running.approved_at is not None,
                )
            except CommandExecutionError as error:
                ExecutionStateMachine.step(running.status, StepStatus.failed)
                failed = self.executions.set_step(
                    step_record_id=running.id,
                    status=StepStatus.failed,
                    error=str(error)[:10_000],
                    finished=True,
                )
                self._compensate(execution, failed, str(error))
                self.uow.commit()
                return True

        try:
            result = self.runner.run(command, running)
        except Exception as error:
            self._fail_or_retry(execution, running, error)
            self.uow.commit()
            return True
        if result.status == "waiting":
            ExecutionStateMachine.step(StepStatus.running, StepStatus.waiting_external)
            self.executions.set_step(
                step_record_id=running.id, status=StepStatus.waiting_external,
                checkpoint=result.checkpoint, external_task_id=result.external_task_id,
            )
            self.uow.commit()
            return True
        self._complete(execution, running, result)
        self.uow.commit()
        return True

    def _complete(self, execution: ExecutionRecord, step: StepExecutionRecord,
                  result: CommandResult) -> None:
        ExecutionStateMachine.step(step.status, StepStatus.completed)
        self.executions.set_step(
            step_record_id=step.id, status=StepStatus.completed, output=result.output,
            checkpoint=result.checkpoint, external_task_id=result.external_task_id,
            error="", clear_next_attempt=True, finished=True,
        )
        self.events.publish(DomainEvent(
            name="agentos.step.completed", workspace_id=execution.workspace_id,
            project_id=execution.project_id, task_id=result.external_task_id,
            payload={"execution_id": execution.id, "step_id": step.step_id,
                     "agent": step.agent, "attempt": step.attempt},
        ))

    def _fail_or_retry(self, execution: ExecutionRecord, step: StepExecutionRecord,
                       error: Exception) -> None:
        message = str(error)[:10_000]
        if step.attempt < step.max_attempts:
            ExecutionStateMachine.step(step.status, StepStatus.retry_wait)
            retry_at = now() + timedelta(seconds=min(60, 2 ** max(step.attempt - 1, 0)))
            self.executions.set_step(
                step_record_id=step.id, status=StepStatus.retry_wait,
                error=message, next_attempt_at=retry_at, finished=True,
            )
            self.events.publish(DomainEvent(
                name="agentos.step.retry_scheduled", workspace_id=execution.workspace_id,
                project_id=execution.project_id,
                payload={"execution_id": execution.id, "step_id": step.step_id,
                         "attempt": step.attempt, "next_attempt_at": retry_at.isoformat()},
            ))
            return
        ExecutionStateMachine.step(step.status, StepStatus.failed)
        failed = self.executions.set_step(
            step_record_id=step.id, status=StepStatus.failed, error=message, finished=True
        )
        self._compensate(execution, failed, message)

    def _compensate(self, execution: ExecutionRecord, failed: StepExecutionRecord,
                    reason: str) -> None:
        ExecutionStateMachine.execution(execution.status, ExecutionStatus.compensating)
        self.executions.set_execution(
            execution_id=execution.id, status=ExecutionStatus.compensating,
            failure_reason=reason, current_step_id=failed.step_id,
        )
        compensation_errors = []
        completed = [s for s in self.steps(execution_id=execution.id)
                     if s.status == StepStatus.completed]
        for step in reversed(completed):
            try:
                details = self.runner.compensate(restore_command(step), step)
                ExecutionStateMachine.step(step.status, StepStatus.compensated)
                checkpoint = dict(step.checkpoint)
                checkpoint["compensation"] = details
                self.executions.set_step(
                    step_record_id=step.id, status=StepStatus.compensated, checkpoint=checkpoint
                )
            except Exception as error:
                compensation_errors.append(f"{step.step_id}: {str(error)[:1000]}")
        target = ExecutionStatus.compensated if not compensation_errors else ExecutionStatus.failed
        ExecutionStateMachine.execution(ExecutionStatus.compensating, target)
        self.executions.set_execution(
            execution_id=execution.id, status=target, failure_reason=reason,
            checkpoint={"failed_step": failed.step_id,
                        "compensation_errors": compensation_errors}, completed=True,
        )
        self.events.publish(DomainEvent(
            name="agentos.execution.compensated" if not compensation_errors else "agentos.execution.failed",
            workspace_id=execution.workspace_id, project_id=execution.project_id,
            outcome="failed", payload={"execution_id": execution.id,
                                       "failed_step": failed.step_id,
                                       "compensation_errors": compensation_errors},
        ))
