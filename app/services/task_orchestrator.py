from __future__ import annotations

import json
import os
import signal
import subprocess
import time
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
LEASE_SECONDS = 7200


def now() -> datetime:
    return datetime.now(timezone.utc)


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


def runtime_view(db: Session, task: Task) -> dict:
    runtime = _runtime(db, task.id)
    state = _state(task, runtime)
    decision = evaluate_task(task.prompt, task.requires_approval and task.approved_at is None)
    gate = state == "awaiting_approval" or (decision.requires_approval and task.approved_at is None)
    if gate:
        next_action = "approve"
    elif state == "paused":
        next_action = "resume"
    elif state in {"queued", "failed"}:
        next_action = "execute"
    elif state == "running":
        next_action = "wait"
    else:
        next_action = "none"
    return {
        "task_id": task.id,
        "state": state,
        "version": int(runtime["version"] if runtime else 0),
        "auto_advance": bool(runtime["auto_advance"] if runtime else False),
        "claim_owner": str(runtime["claim_owner"] or "") if runtime else "",
        "lease_expires_at": runtime["lease_expires_at"] if runtime else None,
        "last_action": str(runtime["last_action"] or "") if runtime else "",
        "last_message": str(runtime["last_message"] or "") if runtime else "",
        "archived_at": runtime["archived_at"] if runtime else None,
        "next_action": next_action,
        "gate": {"blocked": gate, "reasons": list(decision.reasons)},
        "learning": learning_events(db, task.id, 12),
    }


class TaskOrchestrator:
    def __init__(self, db: Session, actor: str = "owner"):
        self.db = db
        self.actor = actor
        ensure_orchestrator_schema()

    def _task(self, task_id: str) -> Task:
        task = self.db.get(Task, task_id)
        if task is None:
            raise LookupError("Task not found")
        return task

    def _audit(self, task: Task, action: str, outcome: str = "success", details: dict | None = None) -> None:
        record(
            self.db,
            workspace_id=task.workspace_id,
            project_id=task.project_id,
            task_id=task.id,
            actor=self.actor,
            action=action,
            outcome=outcome,
            details=details or {},
        )

    def next(self, task_id: str) -> dict:
        task = self._task(task_id)
        runtime = _runtime(self.db, task.id)
        state = _state(task, runtime)
        if state in {"archived", "running", "pause_requested", "cancel_requested", "completed", "canceled"}:
            return runtime_view(self.db, task)
        decision = evaluate_task(task.prompt, task.requires_approval and task.approved_at is None)
        if decision.requires_approval and task.approved_at is None:
            task.status = TaskStatus.awaiting_approval
            _set_runtime(self.db, task, "awaiting_approval", "next", "Fluxo parado no gate de autorização explícita.", auto=False)
            self._audit(task, "task.orchestrator.gate", "blocked", {"reasons": decision.reasons})
            self.db.commit()
            return runtime_view(self.db, task)
        if task.status in {TaskStatus.failed, TaskStatus.blocked, TaskStatus.awaiting_approval} or state == "paused":
            task.status = TaskStatus.queued
        _set_runtime(self.db, task, "queued", "next", "Próxima ação segura colocada na fila sem duplicar execução.")
        _learn(
            self.db,
            task,
            "next",
            "O orquestrador calculou uma única transição segura.",
            "Todos os canais devem usar a mesma máquina de estados.",
            "Idempotência e máquina de estados",
            "Estado persistido e gate antes da execução.",
            "Repetir Próximo não cria uma segunda execução.",
            {"from": state, "to": "queued"},
        )
        self._audit(task, "task.orchestrator.next", details={"from": state, "to": "queued"})
        self.db.commit()
        return runtime_view(self.db, task)

    def auto_advance(self, task_id: str) -> dict:
        task = self._task(task_id)
        runtime = _runtime(self.db, task.id)
        _set_runtime(self.db, task, _state(task, runtime), "auto_advance", "Avanço automático habilitado até o próximo gate crítico.", auto=True)
        self._audit(task, "task.orchestrator.auto_enabled")
        self.db.commit()
        return self.next(task_id)

    def pause(self, task_id: str) -> dict:
        task = self._task(task_id)
        runtime = _runtime(self.db, task.id)
        state = _state(task, runtime)
        if state in TERMINAL_STATES | {"paused", "pause_requested"}:
            return runtime_view(self.db, task)
        target = "pause_requested" if task.status == TaskStatus.running else "paused"
        _set_runtime(self.db, task, target, "pause", "Pausa cooperativa solicitada." if target.endswith("requested") else "Tarefa pausada antes da execução.", auto=False)
        self._audit(task, "task.orchestrator.pause", "requested" if target.endswith("requested") else "success", {"from": state, "to": target})
        self.db.commit()
        return runtime_view(self.db, task)

    def resume(self, task_id: str) -> dict:
        task = self._task(task_id)
        state = _state(task, _runtime(self.db, task.id))
        if state not in {"paused", "pause_requested"}:
            return runtime_view(self.db, task)
        task.status = TaskStatus.queued
        _set_runtime(self.db, task, "queued", "resume", "Tarefa retomada sem apagar runs ou evidências.")
        _learn(
            self.db,
            task,
            "resume",
            "A tarefa voltou à fila preservando o histórico.",
            "Pausa controla trabalho futuro e não simula rollback.",
            "Execução retomável",
            "Runs e auditoria anteriores continuam registrados.",
            "Retomar reaproveita estado persistido sem apagar efeitos reais.",
        )
        self._audit(task, "task.orchestrator.resume", details={"from": state, "to": "queued"})
        self.db.commit()
        return runtime_view(self.db, task)

    def cancel(self, task_id: str) -> dict:
        task = self._task(task_id)
        state = _state(task, _runtime(self.db, task.id))
        if state in {"archived", "canceled"}:
            return runtime_view(self.db, task)
        target = "cancel_requested" if task.status == TaskStatus.running else "canceled"
        if target == "canceled" and task.status == TaskStatus.queued:
            task.status = TaskStatus.failed
        _set_runtime(self.db, task, target, "cancel", "Cancelamento cooperativo solicitado." if target.endswith("requested") else "Tarefa cancelada antes de nova execução.", auto=False)
        self._audit(task, "task.orchestrator.cancel", "requested" if target.endswith("requested") else "success", {"from": state, "to": target})
        self.db.commit()
        return runtime_view(self.db, task)

    def archive(self, task_id: str) -> dict:
        task = self._task(task_id)
        state = _state(task, _runtime(self.db, task.id))
        if task.status == TaskStatus.running or state in {"pause_requested", "cancel_requested"}:
            raise RuntimeError("Running task must be stopped before archive")
        _set_runtime(self.db, task, "archived", "archive", "Arquivamento lógico concluído; runs e auditoria preservados.", auto=False, archive=now())
        self._audit(task, "task.orchestrator.archived", details={"previous_state": state, "history_preserved": True})
        self.db.commit()
        return runtime_view(self.db, task)


def _recover_expired_claims(db: Session) -> None:
    ensure_orchestrator_schema()
    expired = db.execute(
        select(TASK_RUNTIME.c.task_id).where(
            TASK_RUNTIME.c.state == "running",
            TASK_RUNTIME.c.lease_expires_at.is_not(None),
            TASK_RUNTIME.c.lease_expires_at < now(),
        )
    ).scalars().all()
    for task_id in expired:
        task = db.get(Task, task_id)
        if task and task.status == TaskStatus.running:
            task.status = TaskStatus.queued
            _set_runtime(db, task, "queued", "lease_recovered", "Lease expirado recuperado; tarefa devolvida à fila.", owner="", lease=None)
            record(db, workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor="worker", action="task.orchestrator.lease_recovered", outcome="success", details={})
    if expired:
        db.commit()


def claim_next_task(db: Session, owner: str) -> Task | None:
    """Acquire one queued task with compare-and-set semantics across concurrent workers."""
    ensure_orchestrator_schema()
    _recover_expired_claims(db)
    for _ in range(8):
        stopped = exists(
            select(TASK_RUNTIME.c.task_id).where(
                TASK_RUNTIME.c.task_id == Task.id,
                TASK_RUNTIME.c.state.in_(tuple(STOP_STATES)),
            )
        )
        candidate = (
            select(Task.id)
            .where(Task.status == TaskStatus.queued, ~stopped)
            .order_by(Task.priority.desc(), Task.created_at, Task.id)
            .limit(1)
            .scalar_subquery()
        )
        task_id = db.scalar(
            update(Task)
            .where(Task.id == candidate, Task.status == TaskStatus.queued)
            .values(status=TaskStatus.running)
            .returning(Task.id)
        )
        if not task_id:
            db.rollback()
            return None
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
        lease = now() + timedelta(seconds=LEASE_SECONDS)
        _set_runtime(db, task, "running", "claim", "Worker adquiriu posse atômica da tarefa.", owner=owner, lease=lease)
        record(db, workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor=owner, action="task.orchestrator.claimed", outcome="success", details={"atomic": True, "lease_seconds": LEASE_SECONDS})
        db.commit()
        return task
    return None


def requested_control(task_id: str) -> str:
    with SessionLocal() as db:
        row = _runtime(db, task_id)
        return str(row["state"]) if row else ""


def mark_worker_controlled(db: Session, task: Task, requested: str, message: str) -> None:
    target = "paused" if requested == "pause_requested" else "canceled"
    task.status = TaskStatus.queued if target == "paused" else TaskStatus.failed
    _set_runtime(db, task, target, "worker_control", message, auto=False, owner="", lease=None)
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
    mission.status = QuestMissionStatus.completed.value
    mission.completed_at = now()
    mission.validation_summary = summary
    mission.evidence_json = json.dumps({"run_id": run.id, "run_status": run.status, "commit_sha": run.commit_sha, "pull_request_url": run.pull_request_url}, ensure_ascii=False)
    record(
        db,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        task_id=task.id,
        actor="worker",
        action="QUEST_REWARD_GRANTED",
        outcome="success",
        details={"mission_id": mission.id, "reward": {"xp": reward.xp, "stars": reward.stars, "moons": reward.moons, "swords": reward.swords}, "automatic": True, "rbac_unchanged": True},
    )


def mark_worker_finished(db: Session, task: Task, run: Run) -> None:
    state = "completed" if run.status == "success" else ("blocked" if task.status == TaskStatus.blocked else "failed")
    _set_runtime(db, task, state, "worker_finished", str(run.summary or ""), owner="", lease=None)
    _learn(
        db,
        task,
        state,
        "A execução terminou com evidência persistida no run.",
        "Conclusão, aprendizado e recompensa só usam o resultado real do executor.",
        "Conclusão baseada em evidência",
        "Status, resumo, commit e pull request quando registrados.",
        "Uma mensagem de sucesso não substitui evidência persistida.",
        {"run_id": run.id, "run_status": run.status, "commit_sha": run.commit_sha, "pull_request_url": run.pull_request_url},
    )
    if state == "completed":
        _grant_quest_reward(db, task, run)


@contextmanager
def controlled_executor_run(task: Task, original_run: Callable):
    """Yield a subprocess runner that can terminate the active Codex process group."""
    def controlled(args, cwd=None, timeout=900, env_overrides=None):
        if not args or os.path.basename(str(args[0])) != "codex":
            return original_run(args, cwd=cwd, timeout=timeout, env_overrides=env_overrides)
        environment = os.environ.copy()
        if env_overrides:
            environment.update(env_overrides)
        # Codex is always a non-interactive worker process.  Giving it a closed stdin
        # prevents CLI versions from waiting for "additional input from stdin" and
        # leaving the pipeline permanently stuck/failed.
        environment.setdefault("CI", "1")
        environment.setdefault("DEBIAN_FRONTEND", "noninteractive")
        process = subprocess.Popen(
            args,
            cwd=cwd,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=True,
        )
        started = time.monotonic()
        while process.poll() is None:
            control = requested_control(task.id)
            if control in {"pause_requested", "cancel_requested"}:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    stdout, stderr = process.communicate()
                return subprocess.CompletedProcess(args, 130, stdout or "", (stderr or "") + f"\nDevPilot {control}")
            if time.monotonic() - started >= timeout:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(args, timeout, output=stdout, stderr=stderr)
            time.sleep(0.4)
        stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(args, int(process.returncode or 0), stdout or "", stderr or "")

    yield controlled
