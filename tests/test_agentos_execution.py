from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agentos.application.execution import GraphExecutionService
from app.agentos.application.planning import DeterministicPlanningStrategy
from app.agentos.application.ports import CommandResult, GoalRecord
from app.agentos.domain.execution import ExecutionStateMachine, ExecutionStatus, StateTransitionError
from app.agentos.infrastructure.execution import SQLAlchemyExecutionRepository
from app.db import Base


class GoalRepo:
    def __init__(self, goal: GoalRecord) -> None:
        self.goal = goal

    def get(self, *, workspace_id: str, goal_id: str):
        if workspace_id == self.goal.workspace_id and goal_id == self.goal.id:
            return self.goal
        return None


class Runner:
    def run(self, command, step):
        return CommandResult(
            status="completed",
            output={"agent": command.agent, "attempt": step.attempt},
            checkpoint={"step": step.step_id},
        )

    def poll(self, command, step):
        return CommandResult(status="waiting")

    def compensate(self, command, step):
        return {"action": "noop"}


class Events:
    def __init__(self) -> None:
        self.items = []

    def publish(self, event) -> None:
        self.items.append(event)


class Uow:
    def __init__(self, db: Session) -> None:
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()


def service_for(objective: str):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    plan = DeterministicPlanningStrategy().plan(objective)
    goal = GoalRecord(
        id="goal-1",
        workspace_id="workspace-1",
        project_id="project-1",
        title="Test goal",
        objective=objective,
        status="planned",
        plan=plan,
        created_at=datetime.now(timezone.utc),
    )
    events = Events()
    service = GraphExecutionService(
        goals=GoalRepo(goal),
        executions=SQLAlchemyExecutionRepository(db),
        runner=Runner(),
        events=events,
        uow=Uow(db),
    )
    return db, service, events


def drive(service: GraphExecutionService, limit: int = 50) -> None:
    for _ in range(limit):
        if not service.process_one():
            break


def test_execution_is_idempotent_and_checkpoints_graph():
    db, service, events = service_for("Implement a backend API")
    try:
        first = service.start(
            workspace_id="workspace-1",
            goal_id="goal-1",
            idempotency_key="same-request-key",
        )
        second = service.start(
            workspace_id="workspace-1",
            goal_id="goal-1",
            idempotency_key="same-request-key",
        )
        assert first.id == second.id

        drive(service)
        completed = service.get(workspace_id="workspace-1", execution_id=first.id)
        assert completed is not None
        assert completed.status == ExecutionStatus.completed
        steps = service.steps(execution_id=first.id)
        assert steps
        assert all(step.status == "completed" for step in steps)
        assert all(step.checkpoint for step in steps)
        assert any(event.name == "agentos.execution.completed" for event in events.items)
    finally:
        db.close()


def test_delivery_waits_for_explicit_approval_then_resumes():
    db, service, _ = service_for("Implement an API and deploy it with Docker")
    try:
        execution = service.start(
            workspace_id="workspace-1",
            goal_id="goal-1",
            idempotency_key="approval-test",
        )
        drive(service)
        waiting = service.get(workspace_id="workspace-1", execution_id=execution.id)
        assert waiting is not None
        assert waiting.status == ExecutionStatus.awaiting_approval
        delivery = next(step for step in service.steps(execution_id=execution.id)
                        if step.step_id == "delivery")
        assert delivery.status == "awaiting_approval"

        service.approve_step(
            workspace_id="workspace-1",
            execution_id=execution.id,
            step_id="delivery",
        )
        drive(service)
        completed = service.get(workspace_id="workspace-1", execution_id=execution.id)
        assert completed is not None
        assert completed.status == ExecutionStatus.completed
    finally:
        db.close()


def test_state_machine_rejects_invalid_terminal_transition():
    try:
        ExecutionStateMachine.execution("completed", "running")
    except StateTransitionError:
        pass
    else:
        raise AssertionError("completed execution must be terminal")
