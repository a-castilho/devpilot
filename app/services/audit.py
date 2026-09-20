from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.linux_agent.audit import verify_attestation
from app.models import AuditEvent, Project, Task, Workspace
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError


LINUX_AUDIT_KEY = "_linux_audit"
_SCOPE_DISABLED_OPTION = "devpilot_account_scope_disabled"


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


def _sqlite_workspace_write_lock_statement(workspace_id: str):
    # SQLite has no SELECT ... FOR UPDATE. A no-op UPDATE obtains its transaction
    # write lock before the audit head is read. Concurrent writers therefore wait
    # (or fail with SQLITE_BUSY on a stale snapshot) instead of forking the chain.
    return (
        update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(slug=Workspace.slug)
    )


def _lock_workspace_audit_chain(db: Session, workspace_id: str) -> None:
    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        db.execute(
            _sqlite_workspace_write_lock_statement(workspace_id).execution_options(
                **{_SCOPE_DISABLED_OPTION: True}
            )
        )
        return

    db.scalar(
        _workspace_lock_statement(workspace_id).execution_options(
            **{_SCOPE_DISABLED_OPTION: True}
        )
    )


def _previous_hash_for_workspace(db: Session, workspace_id: str) -> str:
    _lock_workspace_audit_chain(db, workspace_id)
    previous_hash = db.scalar(
        select(AuditEvent.event_hash)
        .where(AuditEvent.workspace_id == workspace_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
        .execution_options(**{_SCOPE_DISABLED_OPTION: True})
    )
    return str(previous_hash or "")


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

    # The hash chain is workspace-global even though normal account reads are scoped.
    # Serialize the workspace before reading its head and keep that database lock until
    # the caller commits/rolls back so concurrent transactions cannot create siblings.
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
