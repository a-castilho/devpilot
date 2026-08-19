from __future__ import annotations

from enum import StrEnum


class ExecutionStatus(StrEnum):
    pending = "pending"
    running = "running"
    awaiting_approval = "awaiting_approval"
    compensating = "compensating"
    compensated = "compensated"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StepStatus(StrEnum):
    pending = "pending"
    running = "running"
    waiting_external = "waiting_external"
    retry_wait = "retry_wait"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    compensated = "compensated"
    skipped = "skipped"


TERMINAL_EXECUTION_STATUSES = {
    ExecutionStatus.compensated,
    ExecutionStatus.completed,
    ExecutionStatus.failed,
    ExecutionStatus.cancelled,
}
TERMINAL_STEP_STATUSES = {
    StepStatus.completed,
    StepStatus.failed,
    StepStatus.compensated,
    StepStatus.skipped,
}


class StateTransitionError(RuntimeError):
    pass


_EXECUTION_TRANSITIONS: dict[ExecutionStatus, set[ExecutionStatus]] = {
    ExecutionStatus.pending: {ExecutionStatus.running, ExecutionStatus.cancelled},
    ExecutionStatus.running: {
        ExecutionStatus.awaiting_approval,
        ExecutionStatus.compensating,
        ExecutionStatus.completed,
        ExecutionStatus.failed,
        ExecutionStatus.cancelled,
    },
    ExecutionStatus.awaiting_approval: {
        ExecutionStatus.running,
        ExecutionStatus.cancelled,
    },
    ExecutionStatus.compensating: {
        ExecutionStatus.compensated,
        ExecutionStatus.failed,
    },
    ExecutionStatus.compensated: {ExecutionStatus.running},
    ExecutionStatus.failed: {ExecutionStatus.running},
    ExecutionStatus.completed: set(),
    ExecutionStatus.cancelled: {ExecutionStatus.running},
}

_STEP_TRANSITIONS: dict[StepStatus, set[StepStatus]] = {
    StepStatus.pending: {
        StepStatus.running,
        StepStatus.awaiting_approval,
        StepStatus.skipped,
    },
    StepStatus.awaiting_approval: {StepStatus.pending, StepStatus.skipped},
    StepStatus.running: {
        StepStatus.completed,
        StepStatus.waiting_external,
        StepStatus.retry_wait,
        StepStatus.failed,
    },
    StepStatus.waiting_external: {
        StepStatus.completed,
        StepStatus.retry_wait,
        StepStatus.failed,
    },
    StepStatus.retry_wait: {StepStatus.pending, StepStatus.failed},
    StepStatus.failed: {StepStatus.pending, StepStatus.compensated},
    StepStatus.completed: {StepStatus.compensated},
    StepStatus.compensated: {StepStatus.pending},
    StepStatus.skipped: {StepStatus.pending},
}


class ExecutionStateMachine:
    @staticmethod
    def execution(current: str, target: str) -> ExecutionStatus:
        source = ExecutionStatus(current)
        destination = ExecutionStatus(target)
        if source == destination:
            return destination
        if destination not in _EXECUTION_TRANSITIONS[source]:
            raise StateTransitionError(f"Invalid execution transition: {source} -> {destination}")
        return destination

    @staticmethod
    def step(current: str, target: str) -> StepStatus:
        source = StepStatus(current)
        destination = StepStatus(target)
        if source == destination:
            return destination
        if destination not in _STEP_TRANSITIONS[source]:
            raise StateTransitionError(f"Invalid step transition: {source} -> {destination}")
        return destination
