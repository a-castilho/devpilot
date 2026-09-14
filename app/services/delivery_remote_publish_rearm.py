from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Task, TaskStatus
from app.services.audit import record


REARM_MARKER = "[delivery-remote-publish-v1]"
DELIVERY_MARKER = "[DEVPILOT_DELIVERY_REPAIR_V1]"
_STARTED = False
_LOCK = threading.Lock()


def rearm_exhausted_delivery_repairs_once() -> int:
    """Give previously exhausted deliveries one migration attempt with remote publish enabled."""
    changed = 0
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        tasks = list(
            db.scalars(
                select(Task)
                .where(
                    Task.source == "delivery-recovery",
                    Task.status.in_((TaskStatus.failed, TaskStatus.blocked)),
                    Task.prompt.contains(DELIVERY_MARKER),
                )
                .order_by(Task.created_at.asc())
                .limit(250)
            ).all()
        )
        for task in tasks:
            prompt = str(task.prompt or "")
            if REARM_MARKER in prompt:
                continue
            task.prompt = (
                prompt.rstrip()
                + "\n\n"
                + REARM_MARKER
                + "\nA infraestrutura de entrega foi corrigida para commit/push automático do resultado "
                  "da recuperação final. Execute uma única nova tentativa completa, materialize o produto "
                  "real e deixe os arquivos prontos; o DevPilot publicará e verificará o commit remoto após "
                  "a execução. Não encerre somente com relatório.\n"
            )[:100_000]
            task.status = TaskStatus.queued
            task.requires_approval = False
            task.approved_at = task.approved_at or now
            task.updated_at = now
            record(
                db,
                workspace_id=task.workspace_id,
                project_id=task.project_id,
                task_id=task.id,
                actor="delivery-remote-publish-migration",
                action="project.delivery_repair_rearmed_after_publish_fix",
                outcome="queued",
                details={"one_time": True, "capability": "remote_commit_push_verify"},
            )
            changed += 1
        if changed:
            db.commit()
    return changed


def _run_once() -> None:
    time.sleep(8)
    try:
        count = rearm_exhausted_delivery_repairs_once()
        if count:
            print(f"[delivery-remote-publish] rearmed exhausted repairs={count}", flush=True)
    except Exception as error:
        print(
            f"[delivery-remote-publish] rearm error={type(error).__name__}: {str(error)[:180]}",
            flush=True,
        )


def start_delivery_remote_publish_rearm() -> None:
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True
        threading.Thread(
            target=_run_once,
            name="devpilot-delivery-remote-publish-rearm",
            daemon=True,
        ).start()
