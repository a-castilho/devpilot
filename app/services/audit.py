from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.linux_agent.audit import verify_attestation
from app.models import AuditEvent, Project, Task, Workspace
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError

try:
    import fcntl
except ImportError:  # pragma: no cover - DevPilot runtime targets Linux.
    fcntl = None


LINUX_AUDIT_KEY = "_linux_audit"
_SCOPE_DISABLED_OPTION = "devpilot_account_scope_disabled"
_AUDIT_CHAIN_HEADS_INFO = "_devpilot_audit_chain_heads"
_SQLITE_AUDIT_LOCKS_INFO = "_devpilot_sqlite_audit_locks"
_SQLITE_PROCESS_LOCKS: dict[tuple[str, str], threading.Lock] = {}
_SQLITE_PROCESS_LOCKS_GUARD = threading.Lock()


def _serialize(details: dict[str, Any]) -> str:
    return json.dumps(details, sort_keys=True, separators=(",", ":"), default=str)


def _legacy_hash(
    *,
    previous_hash: str,
    workspace_id: str,
    project_id: str | None,
    task_id: str | None,
    actor: str,
    action: str,
    outcome: str,
    serialized_details: str,
) -> str:
    fingerprint = "|".join(
        [
            previous_hash,
            workspace_id,
            project_id or "",
            task_id or "",
            actor,
            action,
            outcome,
            serialized_details,
        ]
    )
    return hashlib.sha256(fingerprint.encode()).hexdigest()


def _linux_attestation_enabled() -> bool:
    settings = get_settings()
    return len(settings.linux_agent_secret.strip()) >= 32


def _attest(
    *,
    previous_hash: str,
    workspace_id: str,
    project_id: str | None,
    task_id: str | None,
    actor: str,
    action: str,
    outcome: str,
    details: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if not _linux_attestation_enabled():
        return None, "linux_agent_not_configured"

    event_payload = {
        "previous_hash": previous_hash,
        "workspace_id": workspace_id,
        "project_id": project_id or "",
        "task_id": task_id or "",
        "run_id": "",
        "actor": actor,
        "action": action,
        "outcome": outcome,
        "details": details,
    }
    try:
        attestation = LinuxAgentClient().request(
            "POST",
            "/v1/audit/attest",
            payload=event_payload,
        )
    except LinuxAgentError as error:
        return None, str(error)

    valid, reason = verify_attestation(event_payload, attestation)
    if not valid:
        return None, f"invalid_linux_attestation:{reason}"
    return attestation, None


def _event_owner_user_id(
    db: Session,
    *,
    project_id: str | None,
    task_id: str | None,
) -> str | None:
    principal_user_id = db.info.get("principal_user_id")
    if principal_user_id:
        return str(principal_user_id)

    if task_id:
        owner_user_id = db.scalar(
            select(Task.owner_user_id)
            .where(Task.id == task_id)
            .execution_options(**{_SCOPE_DISABLED_OPTION: True})
        )
        if owner_user_id:
            return str(owner_user_id)

    if project_id:
        owner_user_id = db.scalar(
            select(Project.owner_user_id)
            .where(Project.id == project_id)
            .execution_options(**{_SCOPE_DISABLED_OPTION: True})
        )
        if owner_user_id:
            return str(owner_user_id)

    return None


def _workspace_lock_statement(workspace_id: str):
    return select(Workspace.id).where(Workspace.id == workspace_id).with_for_update()


def _audit_head_statement(workspace_id: str):
    return (
        select(AuditEvent.event_hash)
        .where(AuditEvent.workspace_id == workspace_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )


def _sqlite_database_path(db: Session) -> Path | None:
    bind = db.get_bind()
    database = getattr(bind.url, "database", None)
    if not database or database == ":memory:":
        return None
    return Path(str(database)).expanduser().resolve()


def _sqlite_process_lock(db: Session, workspace_id: str) -> threading.Lock:
    key = (str(db.get_bind().url), workspace_id)
    with _SQLITE_PROCESS_LOCKS_GUARD:
        lock = _SQLITE_PROCESS_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SQLITE_PROCESS_LOCKS[key] = lock
    return lock


def _acquire_sqlite_audit_lock(db: Session, workspace_id: str) -> None:
    locks = db.info.setdefault(_SQLITE_AUDIT_LOCKS_INFO, {})
    if workspace_id in locks:
        return

    process_lock = _sqlite_process_lock(db, workspace_id)
    process_lock.acquire()
    lock_file = None
    try:
        database_path = _sqlite_database_path(db)
        if database_path is not None and fcntl is not None:
            database_path.parent.mkdir(parents=True, exist_ok=True)
            suffix = hashlib.sha256(workspace_id.encode()).hexdigest()[:24]
            lock_path = database_path.parent / f".{database_path.name}.audit-{suffix}.lock"
            lock_file = lock_path.open("a+b")
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        locks[workspace_id] = {
            "process_lock": process_lock,
            "lock_file": lock_file,
        }
    except Exception:
        if lock_file is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                lock_file.close()
        process_lock.release()
        raise


def _release_sqlite_audit_locks(session: Session) -> None:
    locks = session.info.pop(_SQLITE_AUDIT_LOCKS_INFO, {})
    for state in locks.values():
        lock_file = state.get("lock_file")
        process_lock = state.get("process_lock")
        if lock_file is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                lock_file.close()
        if process_lock is not None:
            process_lock.release()


def _previous_hash_for_workspace(db: Session, workspace_id: str) -> str:
    heads = db.info.setdefault(_AUDIT_CHAIN_HEADS_INFO, {})
    cached = heads.get(workspace_id)
    if cached is not None:
        return str(cached)

    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        _acquire_sqlite_audit_lock(db, workspace_id)
        database_path = _sqlite_database_path(db)
        if database_path is not None:
            # Read through a separate connection so a request transaction that began
            # before the audit lock was acquired does not reuse a stale SQLite snapshot.
            with bind.connect() as connection:
                previous_hash = connection.execute(
                    _audit_head_statement(workspace_id)
                ).scalar_one_or_none()
        else:
            previous_hash = db.scalar(
                _audit_head_statement(workspace_id).execution_options(
                    **{_SCOPE_DISABLED_OPTION: True}
                )
            )
    else:
        # Serialize writers on the existing workspace row. PostgreSQL keeps this lock
        # until commit/rollback, so the following head read observes the prior writer.
        db.scalar(
            _workspace_lock_statement(workspace_id).execution_options(
                **{_SCOPE_DISABLED_OPTION: True}
            )
        )
        previous_hash = db.scalar(
            _audit_head_statement(workspace_id).execution_options(
                **{_SCOPE_DISABLED_OPTION: True}
            )
        )

    value = str(previous_hash or "")
    heads[workspace_id] = value
    return value


@sqlalchemy_event.listens_for(Session, "after_transaction_end")
def _clear_audit_chain_transaction_state(session: Session, transaction) -> None:
    if transaction.parent is not None:
        return
    session.info.pop(_AUDIT_CHAIN_HEADS_INFO, None)
    _release_sqlite_audit_locks(session)


def record(
    db: Session,
    *,
    workspace_id: str,
    actor: str,
    action: str,
    details: dict,
    project_id: str | None = None,
    task_id: str | None = None,
    outcome: str = "success",
) -> AuditEvent:
    principal_actor = db.info.get("principal_actor")
    if principal_actor and actor in {"owner", "voice-owner"}:
        actor = str(principal_actor)

    # The chain is workspace-global. Serialize the head read and keep the lock until
    # the caller commits or rolls back so concurrent transactions cannot fork it.
    previous_hash = _previous_hash_for_workspace(db, workspace_id)
    owner_user_id = _event_owner_user_id(
        db,
        project_id=project_id,
        task_id=task_id,
    )

    base_details = dict(details)
    base_details.pop(LINUX_AUDIT_KEY, None)
    attestation, attestation_error = _attest(
        previous_hash=previous_hash,
        workspace_id=workspace_id,
        project_id=project_id,
        task_id=task_id,
        actor=actor,
        action=action,
        outcome=outcome,
        details=base_details,
    )

    stored_details = dict(base_details)
    if attestation:
        stored_details[LINUX_AUDIT_KEY] = {
            **attestation,
            "status": "signed",
            "run_id": "",
        }
        event_hash = str(attestation["event_hash"])
    else:
        if attestation_error != "linux_agent_not_configured":
            stored_details[LINUX_AUDIT_KEY] = {
                "schema_version": 2,
                "status": "unavailable",
                "error": attestation_error or "linux_attestation_unavailable",
                "run_id": "",
            }
        serialized_fallback = _serialize(stored_details)
        event_hash = _legacy_hash(
            previous_hash=previous_hash,
            workspace_id=workspace_id,
            project_id=project_id,
            task_id=task_id,
            actor=actor,
            action=action,
            outcome=outcome,
            serialized_details=serialized_fallback,
        )

    event = AuditEvent(
        workspace_id=workspace_id,
        owner_user_id=owner_user_id,
        project_id=project_id,
        task_id=task_id,
        actor=actor,
        action=action,
        outcome=outcome,
        details=_serialize(stored_details),
        previous_hash=previous_hash,
        event_hash=event_hash,
    )
    db.add(event)
    db.info.setdefault(_AUDIT_CHAIN_HEADS_INFO, {})[workspace_id] = event_hash
    return event


def verify_chain(events: Iterable[AuditEvent]) -> dict[str, Any]:
    expected_previous = ""
    checked = 0
    signed = 0
    unsigned = 0
    invalid: list[dict[str, str]] = []

    for event in events:
        checked += 1
        if event.previous_hash != expected_previous:
            invalid.append(
                {
                    "event_id": event.id,
                    "reason": "previous_hash",
                    "expected": expected_previous,
                    "actual": event.previous_hash,
                }
            )

        try:
            stored_details = json.loads(event.details or "{}")
            if not isinstance(stored_details, dict):
                raise ValueError("details_not_object")
        except (TypeError, ValueError, json.JSONDecodeError):
            invalid.append({"event_id": event.id, "reason": "details_json"})
            expected_previous = event.event_hash
            continue

        attestation = stored_details.get(LINUX_AUDIT_KEY)
        if isinstance(attestation, dict) and attestation.get("status") == "signed":
            base_details = dict(stored_details)
            base_details.pop(LINUX_AUDIT_KEY, None)
            payload = {
                "previous_hash": event.previous_hash,
                "workspace_id": event.workspace_id,
                "project_id": event.project_id or "",
                "task_id": event.task_id or "",
                "run_id": str(attestation.get("run_id") or ""),
                "actor": event.actor,
                "action": event.action,
                "outcome": event.outcome,
                "details": base_details,
            }
            valid, reason = verify_attestation(payload, attestation)
            if not valid or str(attestation.get("event_hash") or "") != event.event_hash:
                invalid.append({"event_id": event.id, "reason": f"linux_signature:{reason}"})
            else:
                signed += 1
        else:
            unsigned += 1
            expected_hash = _legacy_hash(
                previous_hash=event.previous_hash,
                workspace_id=event.workspace_id,
                project_id=event.project_id,
                task_id=event.task_id,
                actor=event.actor,
                action=event.action,
                outcome=event.outcome,
                serialized_details=_serialize(stored_details),
            )
            if expected_hash != event.event_hash:
                invalid.append({"event_id": event.id, "reason": "event_hash"})

        expected_previous = event.event_hash

    chain_valid = not invalid
    return {
        "valid": chain_valid,
        "fully_linux_signed": chain_valid and unsigned == 0,
        "events_checked": checked,
        "linux_signed_events": signed,
        "legacy_or_unsigned_events": unsigned,
        "invalid_events": invalid,
        "chain_head": expected_previous,
    }
