from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agentos.application.execution import GraphExecutionService
from app.agentos.application.planning import DeterministicPlanningStrategy
from app.agentos.application.ports import CommandResult, GoalRecord
from app.agentos.catalog import AGENT_CATALOG
from app.agentos.domain.execution import ExecutionStatus, StepStatus
from app.agentos.infrastructure.execution import SQLAlchemyExecutionRepository
from app.db import Base


class GoalRepo:
    def __init__(self, goal: GoalRecord) -> None:
        self.goal = goal

    def get(self, *, workspace_id: str, goal_id: str):
        return self.goal if workspace_id == self.goal.workspace_id and goal_id == self.goal.id else None


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


class FailingRunner:
    def __init__(self, fail_agent: str, fail_times: int) -> None:
        self.fail_agent = fail_agent
        self.fail_times = fail_times
        self.failures = 0
        self.compensated = []

    def run(self, command, step):
        if command.agent == self.fail_agent and self.failures < self.fail_times:
            self.failures += 1
            raise RuntimeError(f"simulated failure for {command.agent}")
        return CommandResult(
            status="completed",
            output={"agent": command.agent},
            checkpoint={"step": step.step_id},
        )

    def poll(self, command, step):
        return CommandResult(status="waiting")

    def compensate(self, command, step):
        self.compensated.append(step.step_id)
        return {"action": "test-compensation", "step_id": step.step_id}


def make_service(runner: FailingRunner):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    plan = DeterministicPlanningStrategy(AGENT_CATALOG).plan("Implement a backend API")
    goal = GoalRecord(
        id="goal-reliability",
        workspace_id="workspace-reliability",
        project_id="project-reliability",
        title="Reliability goal",
        objective="Implement a backend API",
        status="planned",
        plan=plan,
        created_at=datetime.now(timezone.utc),
    )
    events = Events()
    service = GraphExecutionService(
        goals=GoalRepo(goal),
        executions=SQLAlchemyExecutionRepository(db),
        runner=runner,
        events=events,
        uow=Uow(db),
    )
    return db, service, events


def test_transient_failure_enters_bounded_retry_wait():
    runner = FailingRunner("planner", fail_times=1)
    db, service, events = make_service(runner)
    try:
        execution = service.start(
            workspace_id="workspace-reliability",
            goal_id="goal-reliability",
            idempotency_key="retry-reliability",
            max_attempts=2,
        )
        assert service.process_one() is True  # pending -> running
        assert service.process_one() is True  # planner fails -> retry_wait

        planner = next(
            step for step in service.steps(execution_id=execution.id) if step.step_id == "plan"
        )
        assert planner.status == StepStatus.retry_wait
        assert planner.attempt == 1
        assert planner.next_attempt_at is not None
        assert any(event.name == "agentos.step.retry_scheduled" for event in events.items)
    finally:
        db.close()


def test_terminal_failure_runs_saga_compensation_in_reverse_completed_work():
    runner = FailingRunner("architect", fail_times=1)
    db, service, events = make_service(runner)
    try:
        execution = service.start(
            workspace_id="workspace-reliability",
            goal_id="goal-reliability",
            idempotency_key="saga-reliability",
            max_attempts=1,
        )
        assert service.process_one() is True  # pending -> running
        assert service.process_one() is True  # planner completes
        assert service.process_one() is True  # architect fails -> compensation

        current = service.get(
            workspace_id="workspace-reliability",
            execution_id=execution.id,
        )
        assert current is not None
        assert current.status == ExecutionStatus.compensated
        steps = {step.step_id: step for step in service.steps(execution_id=execution.id)}
        assert steps["plan"].status == StepStatus.compensated
        assert steps["architecture"].status == StepStatus.failed
        assert runner.compensated == ["plan"]
        assert any(event.name == "agentos.execution.compensated" for event in events.items)
    finally:
        db.close()
