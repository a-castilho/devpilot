from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Run, Task, TaskStatus


GENERATION_MARKER = "[delivery-recovery-generation:"
_RETRY_RE = re.compile(r"\[delivery-repair-retry:(\d+)\]")
_INSTALLED = False


def current_generation(prompt: str) -> int:
    values = [int(item) for item in re.findall(r"\[delivery-recovery-generation:(\d+)\]", str(prompt or ""))]
    return values[-1] if values else 1


def retry_count_for_current_generation(prompt: str) -> int:
    text = str(prompt or "")
    marker_pos = text.rfind(GENERATION_MARKER)
    if marker_pos >= 0:
        text = text[marker_pos:]
    return len(_RETRY_RE.findall(text))


def reset_for_new_generation(prompt: str, generation: int) -> str:
    text = _RETRY_RE.sub("", str(prompt or "")).rstrip()
    return (
        text
        + "\n\n"
        + f"[delivery-recovery-generation:{generation}]\n"
        + "Nova geração de recuperação: o contador de tentativas foi reiniciado porque a infraestrutura "
          "de publicação mudou. Falhas de gerações anteriores não podem consumir o limite desta geração.\n"
    )[:100_000]


def _latest_failure(task_id: str) -> dict:
    with SessionLocal() as db:
        run = db.scalar(
            select(Run)
            .where(Run.task_id == task_id)
            .order_by(Run.started_at.desc())
            .limit(1)
        )
        if run is None:
            return {}
        details = {}
        try:
            parsed = json.loads(run.logs or "{}")
            if isinstance(parsed, dict):
                details = parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            details = {}
        stderr = str(details.get("stderr") or "").strip()
        summary = str(details.get("summary") or run.summary or "").strip()
        remote = details.get("delivery_remote_publish") if isinstance(details.get("delivery_remote_publish"), dict) else {}
        message = str(remote.get("message") or summary or stderr or "Falha de recuperação sem detalhe técnico persistido.").strip()
        return {
            "run_id": str(run.id),
            "run_status": str(run.status or ""),
            "message": message[:1200],
            "stderr": stderr[-3000:],
            "remote_publish": remote,
            "started_at": run.started_at.isoformat() if run.started_at else "",
            "finished_at": run.finished_at.isoformat() if run.finished_at else "",
        }


def install_delivery_recovery_generation_patch() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import delivery_product_guard as guard
    from app import product_delivery_routes as delivery

    def generation_retry_count(task: Task) -> int:
        return retry_count_for_current_generation(str(task.prompt or ""))

    guard._retry_count = generation_retry_count

    original_state_for_repair = guard._state_for_repair
    if not getattr(original_state_for_repair, "_devpilot_generation_diagnostics", False):
        def state_for_repair(db, project, actor, reasons, paths):
            state = original_state_for_repair(db, project, actor, reasons, paths)
            repair_id = str(state.get("repair_task_id") or "").strip()
            task = db.get(Task, repair_id) if repair_id else None
            if task is not None:
                state["repair_generation"] = current_generation(str(task.prompt or ""))
                state["repair_retry_count"] = generation_retry_count(task)
                if task.status in {TaskStatus.failed, TaskStatus.blocked}:
                    failure = _latest_failure(task.id)
                    if failure:
                        state["last_failure"] = failure
                        state["last_error"] = failure.get("message") or state.get("last_error")
                        state["updated_at"] = datetime.now(timezone.utc).isoformat()
                        delivery.save_delivery(db, project, state)
            return state

        setattr(state_for_repair, "_devpilot_generation_diagnostics", True)
        guard._state_for_repair = state_for_repair

    _INSTALLED = True
