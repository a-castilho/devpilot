from __future__ import annotations

import json
import os
import signal
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, exists, insert, select, update
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Run, Task, TaskStatus
from app.quest_models import QuestMission, QuestMissionStatus, QuestProfile
from app.services.audit import record
from app.services.policy import evaluate_task
from app.services.quest_engine import apply_reward, reward_for, validate_real_task


TASK_RUNTIME = Table(
    "task_orchestrator_runtime",
    Base.metadata,
    Column("task_id", String(36), primary_key=True),
    Column("state", String(32), nullable=False, default="queued", index=True),
    Column("version", Integer, nullable=False, default=1),
    Column("auto_advance", Boolean, nullable=False, default=False),
    Column("claim_owner", String(160), nullable=False, default=""),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("last_action", String(100), nullable=False, default=""),
    Column("last_message", Text, nullable=False, default=""),
    Column("archived_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    extend_existing=True,
)

TASK_LEARNING = Table(
    "task_learning_events",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", String(36), nullable=False, index=True),
    Column("step", String(80), nullable=False),
    Column("happened", Text, nullable=False),
    Column("rationale", Text, nullable=False),
    Column("concept", Text, nullable=False),
    Column("observe", Text, nullable=False),
    Column("learned", Text, nullable=False),
    Column("evidence", Text, nullable=False, default="{}"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    extend_existing=True,
)

TERMINAL_STATES = {"completed", "failed", "blocked", "canceled", "archived"}
STOP_STATES = {"paused", "pause_requested", "canceled", "cancel_requested", "archived"}
CLAIMED_STATES = {"running", "pause_requested", "cancel_requested"}
# Live workers renew their claim every minute while supervising the subprocess. A five-minute
# lease gives enough tolerance for transient DB/network delays while making Render restarts
# recoverable quickly instead of leaving an autonomous task stuck for hours.
LEASE_SECONDS = 300
LEASE_RENEW_INTERVAL_SECONDS = 60
_PROCESS_CLAIMS: dict[str, str] = {}
_PROCESS_CLAIM_RENEWED_AT: dict[str, float] = {}
_LOST_PROCESS_CLAIMS: set[str] = set()


class LostTaskClaim(RuntimeError):
    """Raised when a worker no longer owns the task lease it previously claimed."""


def now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def ensure_orchestrator_schema() -> None:
    Base.metadata.create_all(bind=engine, tables=[TASK_RUNTIME, TASK_LEARNING], checkfirst=True)


def _runtime(db: Session, task_id: str):
    ensure_orchestrator_schema()
    return db.execute(select(TASK_RUNTIME).where(TASK_RUNTIME.c.task_id == task_id)).mappings().first()


def _state(task: Task, runtime) -> str:
    if runtime:
        return str(runtime["state"])
    return task.status.value if isinstance(task.status, TaskStatus) else str(task.status)


def _set_runtime(
    db: Session,
    task: Task,
    state: str,
    action: str,
    message: str,
    *,
    auto: bool | None = None,
    owner: str | None = None,
    lease=None,
    archive=None,
) -> None:
    current = _runtime(db, task.id)
    values = {
        "state": state,
        "version": int(current["version"] if current else 0) + 1,
        "auto_advance": bool(current["auto_advance"] if current else False) if auto is None else bool(auto),
        "claim_owner": str(current["claim_owner"] or "") if current and owner is None else str(owner or ""),
        "lease_expires_at": current["lease_expires_at"] if current and lease is None else lease,
        "last_action": action,
        "last_message": str(message or "")[:4000],
        "archived_at": current["archived_at"] if current and archive is None else archive,
        "updated_at": now(),
    }
    if state in TERMINAL_STATES | {"paused"}:
        values["claim_owner"] = ""
        values["lease_expires_at"] = None
    if current:
        db.execute(update(TASK_RUNTIME).where(TASK_RUNTIME.c.task_id == task.id).values(**values))
    else:
        db.execute(insert(TASK_RUNTIME).values(task_id=task.id, **values))


def _task_claim_token(task: Task) -> str:
    return str(getattr(task, "_devpilot_claim_owner", "") or _PROCESS_CLAIMS.get(task.id, ""))


def _remember_process_claim(task: Task, claim_owner: str) -> None:
    setattr(task, "_devpilot_claim_owner", claim_owner)
    _PROCESS_CLAIMS[task.id] = claim_owner
    _PROCESS_CLAIM_RENEWED_AT[task.id] = time.monotonic()
    _LOST_PROCESS_CLAIMS.discard(task.id)


def _forget_process_claim(task_id: str, claim_owner: str = "", *, lost: bool = False) -> None:
    current = _PROCESS_CLAIMS.get(task_id, "")
    if claim_owner and current and current != claim_owner:
        return
    _PROCESS_CLAIMS.pop(task_id, None)
    _PROCESS_CLAIM_RENEWED_AT.pop(task_id, None)
    if lost:
        _LOST_PROCESS_CLAIMS.add(task_id)


def _runtime_claim_current(runtime, claim_owner: str, point: datetime | None = None) -> bool:
    if not runtime or not claim_owner:
        return False
    lease = _aware(runtime["lease_expires_at"])
    return (
        str(runtime["state"]) in CLAIMED_STATES
        and str(runtime["claim_owner"] or "") == claim_owner
        and lease is not None
        and lease >= (point or now())
    )


def claim_is_current(db: Session, task_id: str, claim_owner: str) -> bool:
    runtime = _runtime(db, task_id)
    return _runtime_claim_current(runtime, claim_owner)


def renew_task_claim(db: Session, task_id: str, claim_owner: str) -> bool:
    """Extend only an unexpired lease still owned by the same fencing token."""
    point = now()
    result = db.execute(
        update(TASK_RUNTIME)
        .where(
            TASK_RUNTIME.c.task_id == task_id,
            TASK_RUNTIME.c.state.in_(tuple(CLAIMED_STATES)),
            TASK_RUNTIME.c.claim_owner == claim_owner,
            TASK_RUNTIME.c.lease_expires_at.is_not(None),
            TASK_RUNTIME.c.lease_expires_at >= point,
        )
        .values(
            lease_expires_at=point + timedelta(seconds=LEASE_SECONDS),
            updated_at=point,
        )
    )
    return int(result.rowcount or 0) == 1


def require_task_claim(db: Session, task: Task) -> str:
    """Fail closed when the current process lost a previously acquired task claim."""
    if task.id in _LOST_PROCESS_CLAIMS:
        raise LostTaskClaim(f"Task claim was already lost: {task.id}")
    claim_owner = _task_claim_token(task)
    if not claim_owner:
        return ""
    if claim_is_current(db, task.id, claim_owner):
        return claim_owner
    _forget_process_claim(task.id, claim_owner, lost=True)
    raise LostTaskClaim(f"Task claim lost before mutation: {task.id}")


def _transition_claimed_runtime(
    db: Session,
    task: Task,
    claim_owner: str,
    *,
    expected_states: tuple[str, ...],
    state: str,
    action: str,
    message: str,
    auto: bool | None = None,
) -> None:
    """Atomically fence a claimed task while publishing its terminal/control transition."""
    point = now()
    values = {
        "state": state,
        "version": TASK_RUNTIME.c.version + 1,
        "claim_owner": "",
        "lease_expires_at": None,
        "last_action": action,
        "last_message": str(message or "")[:4000],
        "updated_at": point,
    }
    if auto is not None:
        values["auto_advance"] = bool(auto)
    result = db.execute(
        update(TASK_RUNTIME)
        .where(
            TASK_RUNTIME.c.task_id == task.id,
            TASK_RUNTIME.c.state.in_(expected_states),
            TASK_RUNTIME.c.claim_owner == claim_owner,
            TASK_RUNTIME.c.lease_expires_at.is_not(None),
            TASK_RUNTIME.c.lease_expires_at >= point,
        )
        .values(**values)
    )
    if int(result.rowcount or 0) != 1:
        _forget_process_claim(task.id, claim_owner, lost=True)
        raise LostTaskClaim(f"Task claim lost during final transition: {task.id}")


def _learn(
    db: Session,
    task: Task,
    step: str,
    happened: str,
    rationale: str,
    concept: str,
    observe: str,
    learned: str,
    evidence: dict | None = None,
) -> None:
    ensure_orchestrator_schema()
    db.execute(
        insert(TASK_LEARNING).values(
            task_id=task.id,
            step=step,
            happened=happened[:4000],
            rationale=rationale[:4000],
            concept=concept[:4000],
            observe=observe[:4000],
            learned=learned[:4000],
            evidence=json.dumps(evidence or {}, ensure_ascii=False, default=str)[:12000],
            created_at=now(),
        )
    )


def learning_events(db: Session, task_id: str, limit: int = 30) -> list[dict]:
    ensure_orchestrator_schema()
    rows = db.execute(
        select(TASK_LEARNING)
        .where(TASK_LEARNING.c.task_id == task_id)
        .order_by(TASK_LEARNING.c.id.desc())
        .limit(limit)
    ).mappings().all()
    result = []
    for row in reversed(rows):
        item = dict(row)
        try:
            item["evidence"] = json.loads(item.get("evidence") or "{}")
        except (TypeError, ValueError):
            item["evidence"] = {}
        result.append(item)
    return result


def _recover_expired_claims(db: Session) -> None:
    """Recover expired or heartbeat-stale worker claims with compare-and-set fencing."""
    ensure_orchestrator_schema()
    point = now()
    stale_cutoff = point - timedelta(seconds=LEASE_SECONDS)
    observed = db.execute(
        select(
            TASK_RUNTIME.c.task_id,
            TASK_RUNTIME.c.claim_owner,
            TASK_RUNTIME.c.lease_expires_at,
            TASK_RUNTIME.c.updated_at,
        ).where(
            TASK_RUNTIME.c.state == "running",
            TASK_RUNTIME.c.lease_expires_at.is_not(None),
            (
                (TASK_RUNTIME.c.lease_expires_at < point)
                | (TASK_RUNTIME.c.updated_at < stale_cutoff)
            ),
        )
    ).mappings().all()
    recovered = False
    for row in observed:
        task_id = str(row["task_id"])
        claim_owner = str(row["claim_owner"] or "")
        observed_updated_at = row["updated_at"]
        task = db.get(Task, task_id)
        if not task or task.status != TaskStatus.running:
            continue
        # A live process renews updated_at at most every minute. Matching the exact
        # observed timestamp fences this recovery against a concurrent heartbeat.
        result = db.execute(
            update(TASK_RUNTIME)
            .where(
                TASK_RUNTIME.c.task_id == task_id,
                TASK_RUNTIME.c.state == "running",
                TASK_RUNTIME.c.claim_owner == claim_owner,
                TASK_RUNTIME.c.updated_at == observed_updated_at,
                TASK_RUNTIME.c.lease_expires_at.is_not(None),
                (
                    (TASK_RUNTIME.c.lease_expires_at < point)
                    | (TASK_RUNTIME.c.updated_at < stale_cutoff)
                ),
            )
            .values(
                state="queued",
                version=TASK_RUNTIME.c.version + 1,
                claim_owner="",
                lease_expires_at=None,
                last_action="lease_recovered",
                last_message="Claim sem heartbeat recuperado; tarefa devolvida à fila.",
                updated_at=point,
            )
        )
        if int(result.rowcount or 0) != 1:
            continue
        task.status = TaskStatus.queued
        record(
            db,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor="worker",
            action="task.orchestrator.lease_recovered",
            outcome="success",
            details={
                "expired_claim_owner": claim_owner,
                "stale_seconds": LEASE_SECONDS,
                "heartbeat_fenced": True,
            },
        )
        recovered = True
    if recovered:
        db.commit()


def claim_next_task(db: Session, owner: str) -> Task | None:
    """Acquire one queued task with portable compare-and-set semantics across workers."""
    ensure_orchestrator_schema()
    _recover_expired_claims(db)
    for _ in range(8):
        stopped = exists(
            select(TASK_RUNTIME.c.task_id).where(
                TASK_RUNTIME.c.task_id == Task.id,
                TASK_RUNTIME.c.state.in_(tuple(STOP_STATES)),
            )
        )
        task_id = db.scalar(
            select(Task.id)
            .where(Task.status == TaskStatus.queued, ~stopped)
            .order_by(Task.priority.desc(), Task.created_at, Task.id)
            .limit(1)
        )
        if not task_id:
            db.rollback()
            return None
        result = db.execute(
            update(Task)
            .where(Task.id == task_id, Task.status == TaskStatus.queued)
            .values(status=TaskStatus.running)
        )
        if int(result.rowcount or 0) != 1:
            db.rollback()
            continue
        task = db.get(Task, task_id)
        if task is None:
            db.rollback()
            return None
        decision = evaluate_task(task.prompt, task.requires_approval and task.approved_at is None)
        if decision.requires_approval and task.approved_at is None:
            task.status = TaskStatus.awaiting_approval
            _set_runtime(db, task, "awaiting_approval", "claim_gate", "Worker encontrou gate crítico e não iniciou a execução.", auto=False)
            record(db, workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor=owner, action="task.orchestrator.gate", outcome="blocked", details={"reasons": decision.reasons})
            db.commit()
            continue
        claim_owner = f"{str(owner)[:120]}:{uuid.uuid4().hex}"
        lease = now() + timedelta(seconds=LEASE_SECONDS)
        _set_runtime(db, task, "running", "claim", "Worker adquiriu posse atômica da tarefa.", owner=claim_owner, lease=lease)
        record(
            db,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor=owner,
            action="task.orchestrator.claimed",
            outcome="success",
            details={"atomic": True, "lease_seconds": LEASE_SECONDS, "fenced": True},
        )
        db.commit()
        _remember_process_claim(task, claim_owner)
        return task
    return None


def requested_control(task_id: str) -> str:
    if task_id in _LOST_PROCESS_CLAIMS:
        raise LostTaskClaim(f"Task claim was already lost while executing: {task_id}")
    with SessionLocal() as db:
        row = _runtime(db, task_id)
        claim_owner = _PROCESS_CLAIMS.get(task_id, "")
        if claim_owner:
            if not _runtime_claim_current(row, claim_owner):
                _forget_process_claim(task_id, claim_owner, lost=True)
                raise LostTaskClaim(f"Task claim lost while executing: {task_id}")
            last_renewed = _PROCESS_CLAIM_RENEWED_AT.get(task_id, 0.0)
            if time.monotonic() - last_renewed >= LEASE_RENEW_INTERVAL_SECONDS:
                if not renew_task_claim(db, task_id, claim_owner):
                    db.rollback()
                    _forget_process_claim(task_id, claim_owner, lost=True)
                    raise LostTaskClaim(f"Task claim could not be renewed: {task_id}")
                db.commit()
                _PROCESS_CLAIM_RENEWED_AT[task_id] = time.monotonic()
        return str(row["state"]) if row else ""


def mark_worker_controlled(db: Session, task: Task, requested: str, message: str) -> None:
    claim_owner = require_task_claim(db, task)
    target = "paused" if requested == "pause_requested" else "canceled"
    if claim_owner:
        _transition_claimed_runtime(
            db,
            task,
            claim_owner,
            expected_states=(requested,),
            state=target,
            action="worker_control",
            message=message,
            auto=False,
        )
    else:
        _set_runtime(db, task, target, "worker_control", message, auto=False, owner="", lease=None)
    task.status = TaskStatus.queued if target == "paused" else TaskStatus.failed
    _learn(
        db,
        task,
        target,
        message,
        "O executor observou o pedido persistido e encerrou o process group ativo.",
        "Cancelamento cooperativo",
        "Efeitos já aplicados permanecem auditáveis.",
        "Parar não apaga evidências nem promete rollback automático.",
        {"requested": requested},
    )
    record(db, workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor="worker", action=f"task.orchestrator.{target}", outcome="success", details={"cooperative": True})
    if claim_owner:
        _forget_process_claim(task.id, claim_owner)


def _grant_quest_reward(db: Session, task: Task, run: Run) -> None:
    if run.status != "success" or task.status != TaskStatus.completed:
        return
    mission = db.scalar(select(QuestMission).where(QuestMission.workspace_id == task.workspace_id, QuestMission.task_id == task.id))
    if not mission or mission.status == QuestMissionStatus.completed.value or not mission.user_id:
        return
    if mission.status != QuestMissionStatus.accepted.value:
        return
    valid, summary = validate_real_task(task, mission.risk_level)
    if not valid:
        return
    profile = db.scalar(select(QuestProfile).where(QuestProfile.workspace_id == task.workspace_id, QuestProfile.user_id == mission.user_id))
    if profile is None:
        profile = QuestProfile(workspace_id=task.workspace_id, user_id=mission.user_id)
        db.add(profile)
        db.flush()
    reward = reward_for(mission.risk_level, mission.difficulty)
    apply_reward(profile, reward)
