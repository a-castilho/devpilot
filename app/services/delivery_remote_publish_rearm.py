from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Task, TaskStatus
from app.services.audit import record
from app.services.delivery_recovery_generation import current_generation, reset_for_new_generation


REARM_MARKER = "[delivery-remote-publish-v2]"
LEGACY_REARM_MARKER = "[delivery-remote-publish-v1]"
DELIVERY_MARKER = "[DEVPILOT_DELIVERY_REPAIR_V1]"
_STARTED = False
_LOCK = threading.Lock()


def rearm_exhausted_delivery_repairs_once() -> int:
    """Give exhausted deliveries one fresh generation after the remote-publish fix.

    Old retry markers are deliberately removed. They belong to a previous execution
    contract and must not consume the bounded retries of the new publish-capable
    generation.
    """
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

            generation = max(2, current_generation(prompt) + 1)
            prompt = reset_for_new_generation(prompt, generation)
            prompt = prompt.rstrip() + "\n\n" + REARM_MARKER + "\n"
            if LEGACY_REARM_MARKER in prompt:
                prompt += (
                    "A tentativa de migração anterior usou o contador legado e não é válida como tentativa "
                    "desta geração.\n"
                )
            prompt += (
                "A infraestrutura de entrega agora exige commit, push e prova do SHA remoto. Execute uma "
                "nova tentativa completa, materialize o produto real e não encerre apenas com relatório.\n"
            )

            task.prompt = prompt[:100_000]
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
                details={
                    "one_time": True,
                    "generation": generation,
                    "capability": "remote_commit_push_verify",
                    "legacy_retries_reset": True,
                },
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
