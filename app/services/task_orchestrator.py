from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text, and_, exists, insert, select, update
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import Project, Run, Task, TaskStatus
from app.services.audit import record
from app.services.policy import evaluate_task


_metadata = MetaData()

TASK_RUNTIME = Table(
    "task_orchestrator_runtime",
    _metadata,
    Column("task_id", String(36), ForeignKey("tasks.id"), primary_key=True),
    Column("state", String(32), nullable=False, default="queued", index=True),
    Column("version", Integer, nullable=False, default=1),
    Column("auto_advance", Boolean, nullable=False, default=False),
    Column("claim_owner", String(160), nullable=False, default=""),
    Column("lease_expires_at", DateTime(timezone=True), nullable=True),
    Column("last_action", String(100), nullable=False, default=""),
    Column("last_message", Text, nullable=False, default=""),
    Column("archived_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

TASK_LEARNING = Table(
    "task_learning_events",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", String(36), ForeignKey("tasks.id"), nullable=False, index=True),
    Column("step", String(80), nullable=False),
    Column("happened", Text, nullable=False),
    Column("rationale", Text, nullable=False),
    Column("concept", Text, nullable=False),
    Column("observe", Text, nullable=False),
    Column("learned", Text, nullable=False),
    Column("evidence", Text, nullable=False, default="{}"),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

TERMINAL_RUNTIME_STATES = {"completed", "failed", "blocked", "canceled", "archived"}
STOP_STATES = {"paused", "pause_requested", "canceled", "cancel_requested", "archived"}


def now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_orchestrator_schema() -> None:
    _metadata.create_all(bind=engine, checkfirst=True)


def _runtime_row(db: Session, task_id: str):
    ensure_orchestrator_schema()
    return db.execute(select(TASK_RUNTIME).where(TASK_RUNTIME.c.task_id == task_id)).mappings().first()


def _task_state(task: Task, runtime) -> str:
    if runtime:
        return str(runtime["state"])
    return task.status.value if isinstance(task.status, TaskStatus) else str(task.status)


def _write_runtime(
    db: Session,
    task: Task,
    *,
    state: str,
    action: str,
    message: str,
    auto_advance: bool | None = None,
    claim_owner: str | None = None,
    lease_expires_at=None,
    archived_at=None,
) -> None:
    current = _runtime_row(db, task.id)
    values = {
        "state": state,
        "version": int(current["version"] if current else 0) + 1,
        "last_action": action,
        "last_message": message[:4000],
        "updated_at": now(),
    }
    if auto_advance is not None:
        values["auto_advance"] = auto_advance
    elif current:
        values["auto_advance"] = bool(current["auto_advance"])
    if claim_owner is not None:
        values["claim_owner"] = claim_owner
    elif current:
        values["claim_owner"] = str(current["claim_owner"] or "")
    if lease_expires_at is not None or (current and state in TERMINAL_RUNTIME_STATES | {"paused"}):
        values["lease_expires_at"] = lease_expires_at
    elif current:
        values["lease_expires_at"] = current["lease_expires_at"]
    if archived_at is not None:
        values["archived_at"] = archived_at
    elif current:
        values["archived_at"] = current["archived_at"]

    if current:
        db.execute(update(TASK_RUNTIME).where(TASK_RUNTIME.c.task_id == task.id).values(**values))
    else:
        values.setdefault("auto_advance", False)
        values.setdefault("claim_owner", "")
        values.setdefault("lease_expires_at", None)
        values.setdefault("archived_at", None)
        db.execute(insert(TASK_RUNTIME).values(task_id=task.id, **values))


def _learning(
    db: Session,
    task: Task,
    *,
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
    runtime = _runtime_row(db, task.id)
    state = _task_state(task, runtime)
    decision = evaluate_task(task.prompt, task.requires_approval and task.approved_at is None)
    gate = state == "awaiting_approval" or (decision.requires_approval and task.approved_at is None)
    next_action = "none"
    if state == "paused":
        next_action = "resume"
    elif state in {"queued", "failed"} and not gate:
        next_action = "execute"
    elif state == "awaiting_approval" or gate:
        next_action = "approve"
    elif state == "running":
        next_action = "wait"
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
        "learning": learning_events(db, task.id, limit=12),
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

    def _audit(self, task: Task, action: str, outcome: str, details: dict | None = None) -> None:
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
        runtime = _runtime_row(self.db, task.id)
        state = _task_state(task, runtime)
        decision = evaluate_task(task.prompt, task.requires_approval and task.approved_at is None)
        if state == "archived":
            return runtime_view(self.db, task)
        if state in {"running", "pause_requested", "cancel_requested"}:
            return runtime_view(self.db, task)
        if decision.requires_approval and task.approved_at is None:
            _write_runtime(self.db, task, state="awaiting_approval", action="next", message="Aguardando autorização explícita.")
            self._audit(task, "task.orchestrator.gate", "blocked", {"reasons": decision.reasons})
            self.db.commit()
            return runtime_view(self.db, task)
        if state == "paused":
            task.status = TaskStatus.queued
            _write_runtime(self.db, task, state="queued", action="next", message="Tarefa retomada e devolvida à fila segura.")
        elif task.status in {TaskStatus.failed, TaskStatus.blocked}:
            task.status = TaskStatus.queued
            _write_runtime(self.db, task, state="queued", action="next", message="Nova tentativa enfileirada de forma idempotente.")
        elif task.status == TaskStatus.awaiting_approval and task.approved_at is not None:
            task.status = TaskStatus.queued
            _write_runtime(self.db, task, state="queued", action="next", message="Autorização registrada; tarefa enfileirada.")
        elif task.status == TaskStatus.queued:
            _write_runtime(self.db, task, state="queued", action="next", message="Tarefa já está na fila; nenhuma duplicação criada.")
        else:
            _write_runtime(self.db, task, state=state, action="next", message="Nenhuma transição adicional é necessária.")
        _learning(
            self.db,
            task,
            step="next",
            happened="O orquestrador calculou a próxima transição segura sem criar uma segunda execução.",
            rationale="A transição é centralizada para que botão, chat, voz e automático usem a mesma regra.",
            concept="Máquina de estados idempotente",
            observe="O estado e o gate de autorização antes da execução.",
            learned="Repetir Próximo não deve duplicar efeitos.",
            evidence={"state": state, "status": str(task.status)},
        )
        self._audit(task, "task.orchestrator.next", "success", {"from": state, "to": _task_state(task, _runtime_row(self.db, task.id))})
        self.db.commit()
        return runtime_view(self.db, task)

    def auto_advance(self, task_id: str) -> dict:
        task = self._task(task_id)
        current = _runtime_row(self.db, task.id)
        _write_runtime(
            self.db,
            task,
            state=_task_state(task, current),
            action="auto_advance",
            message="Avanço automático habilitado até o próximo gate crítico.",
            auto_advance=True,
        )
        self._audit(task, "task.orchestrator.auto_enabled", "success")
        self.db.commit()
        return self.next(task_id)

    def pause(self, task_id: str) -> dict:
        task = self._task(task_id)
        runtime = _runtime_row(self.db, task.id)
        state = _task_state(task, runtime)
        if state in {"paused", "pause_requested"}:
            return runtime_view(self.db, task)
        if state in TERMINAL_RUNTIME_STATES:
            return runtime_view(self.db, task)
        if task.status == TaskStatus.running:
            target = "pause_requested"
            message = "Pausa solicitada; o executor interromperá cooperativamente o processo ativo."
        else:
            target = "paused"
            message = "Tarefa pausada antes de iniciar nova execução."
        _write_runtime(self.db, task, state=target, action="pause", message=message, auto_advance=False)
        self._audit(task, "task.orchestrator.pause", "requested" if target.endswith("requested") else "success", {"from": state, "to": target})
        self.db.commit()
        return runtime_view(self.db, task)

    def resume(self, task_id: str) -> dict:
        task = self._task(task_id)
        runtime = _runtime_row(self.db, task.id)
        state = _task_state(task, runtime)
        if state not in {"paused", "pause_requested"}:
            return runtime_view(self.db, task)
        task.status = TaskStatus.queued
        _write_runtime(self.db, task, state="queued", action="resume", message="Tarefa retomada do último estado persistido.")
        _learning(
            self.db,
            task,
            step="resume",
            happened="A tarefa voltou à fila sem apagar runs ou evidências anteriores.",
            rationale="Retomar preserva rastreabilidade e evita fingir rollback de efeitos já aplicados.",
            concept="Execução retomável",
            observe="Runs anteriores permanecem disponíveis.",
            learned="Pausar controla o fluxo; não desfaz automaticamente alterações já realizadas.",
        )
        self._audit(task, "task.orchestrator.resume", "success", {"from": state, "to": "queued"})
        self.db.commit()
        return runtime_view(self.db, task)

    def cancel(self, task_id: str) -> dict:
        task = self._task(task_id)
        runtime = _runtime_row(self.db, task.id)
        state = _task_state(task, runtime)
        if state in {"canceled", "archived"}:
            return runtime_view(self.db, task)
        target = "cancel_requested" if task.status == TaskStatus.running else "canceled"
        _write_runtime(self.db, task, state=target, action="cancel", message="Cancelamento cooperativo solicitado." if target.endswith("requested") else "Tarefa cancelada antes de nova execução.", auto_advance=False)
        self._audit(task, "task.orchestrator.cancel", "requested" if target.endswith("requested") else "success", {"from": state, "to": target})
        self.db.commit()
        return runtime_view(self.db, task)

    def archive(self, task_id: str) -> dict:
        task = self._task(task_id)
        runtime = _runtime_row(self.db, task.id)
        state = _task_state(task, runtime)
        if task.status == TaskStatus.running or state in {"pause_requested", "cancel_requested"}:
            raise RuntimeError("Running task must be stopped before archive")
        _write_runtime(self.db, task, state="archived", action="archive", message="Tarefa arquivada logicamente; runs e auditoria foram preservados.", auto_advance=False, archived_at=now())
        self._audit(task, "task.orchestrator.archived", "success", {"previous_state": state, "history_preserved": True})
        self.db.commit()
        return runtime_view(self.db, task)


def claim_next_task(db: Session, owner: str) -> Task | None:
    """Atomically claim one queued task. Repeated/concurrent workers cannot own the same task."""
    ensure_orchestrator_schema()
    blocked_runtime = exists(
        select(TASK_RUNTIME.c.task_id).where(
            TASK_RUNTIME.c.task_id == Task.id,
            TASK_RUNTIME.c.state.in_(tuple(STOP_STATES)),
        )
    )
    candidate = (
        select(Task.id)
        .where(Task.status == TaskStatus.queued, ~blocked_runtime)
        .order_by(Task.priority.desc(), Task.created_at, Task.id)
        .limit(1)
        .scalar_subquery()
    )
    claimed = db.scalar(
        update(Task)
        .where(Task.id == candidate, Task.status == TaskStatus.queued)
        .values(status=TaskStatus.running)
        .returning(Task.id)
    )
    if not claimed:
        db.rollback()
        return None
    task = db.get(Task, claimed)
    if task is None:
        db.rollback()
        return None
    _write_runtime(db, task, state="running", action="claim", message="Worker adquiriu posse atômica da tarefa.", claim_owner=owner)
    record(db, workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor=owner, action="task.orchestrator.claimed", outcome="success", details={"atomic": True})
    db.commit()
    return task


def requested_control(task_id: str) -> str:
    with SessionLocal() as db:
        row = _runtime_row(db, task_id)
        return str(row["state"]) if row else ""


def mark_worker_controlled(db: Session, task: Task, state: str, message: str) -> None:
    target = "paused" if state == "pause_requested" else "canceled"
    if target == "paused":
        task.status = TaskStatus.queued
    else:
        task.status = TaskStatus.failed
    _write_runtime(db, task, state=target, action="worker_control", message=message, auto_advance=False, claim_owner="", lease_expires_at=None)
    _learning(
        db,
        task,
        step=target,
        happened=message,
        rationale="O executor observou o pedido persistido e encerrou o processo identificável antes de continuar.",
        concept="Cancelamento cooperativo e process group",
        observe="Efeitos já aplicados não são revertidos automaticamente.",
        learned="Parar controla trabalho futuro sem apagar evidências ou fingir rollback.",
        evidence={"requested_state": state},
    )
    record(db, workspace_id=task.workspace_id, project_id=task.project_id, task_id=task.id, actor="worker", action=f"task.orchestrator.{target}", outcome="success", details={"cooperative": True})


def mark_worker_finished(db: Session, task: Task, run: Run) -> None:
    state = "completed" if run.status == "success" else ("blocked" if task.status == TaskStatus.blocked else "failed")
    _write_runtime(db, task, state=state, action="worker_finished", message=str(run.summary or "")[:4000], claim_owner="", lease_expires_at=None)
    _learning(
        db,
        task,
        step="completed" if state == "completed" else state,
        happened="A execução terminou com evidência persistida no run.",
        rationale="O DevPilot só avança o aprendizado e a missão a partir do resultado real do executor.",
        concept="Conclusão baseada em evidência",
        observe="Status do run, resumo, commit e pull request quando existirem.",
        learned="Conclusão válida depende do resultado registrado, não de uma mensagem otimista.",
        evidence={"run_id": run.id, "run_status": run.status, "commit_sha": run.commit_sha, "pull_request_url": run.pull_request_url},
    )


@contextmanager
def controlled_executor_run(task: Task, original_run: Callable):
    """Replace Codex subprocess calls with a cancellable process-group runner for this task."""
    def controlled(args, cwd=None, timeout=900, env_overrides=None):
        if not args or os.path.basename(str(args[0])) != "codex":
            return original_run(args, cwd=cwd, timeout=timeout, env_overrides=env_overrides)
        environment = os.environ.copy()
        if env_overrides:
            environment.update(env_overrides)
        process = subprocess.Popen(
            args,
            cwd=cwd,
            text=True,
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
