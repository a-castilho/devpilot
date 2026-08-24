from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.linux_agent.audit import verify_attestation
from app.models import AuditEvent
from app.services.linux_agent_client import LinuxAgentClient, LinuxAgentError


LINUX_AUDIT_KEY = "_linux_audit"


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

    previous = db.scalar(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == workspace_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(1)
    )
    previous_hash = previous.event_hash if previous else ""

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

    return {
        "valid": not invalid,
        "events_checked": checked,
        "linux_signed_events": signed,
        "legacy_or_unsigned_events": unsigned,
        "invalid_events": invalid,
        "chain_head": expected_previous,
    }
