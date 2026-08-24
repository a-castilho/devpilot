from __future__ import annotations

import json
import stat

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.linux_agent.audit import attest_event, identity_status, verify_attestation
from app.models import AuditEvent, Workspace
from app.services import audit as audit_service


def sample_event(**overrides):
    event = {
        "previous_hash": "",
        "workspace_id": "workspace-1",
        "project_id": "project-1",
        "task_id": "task-1",
        "run_id": "",
        "actor": "user@example.com",
        "action": "task.executed",
        "outcome": "success",
        "details": {"command": "pytest", "exit_code": 0},
    }
    event.update(overrides)
    return event


def test_linux_identity_creates_private_ed25519_key(monkeypatch, tmp_path):
    identity_dir = tmp_path / "identity"
    monkeypatch.setenv("DEVPILOT_LINUX_AUDIT_IDENTITY_DIR", str(identity_dir))

    status = identity_status()

    assert status["signature_algorithm"] == "ed25519"
    assert status["linux_identity"]["username"]
    assert status["linux_identity"]["euid"] >= 0
    assert len(status["signing_key_id"]) == 64
    assert stat.S_IMODE((identity_dir / "audit-private.key").stat().st_mode) == 0o600
    assert (identity_dir / "audit-public.key").is_file()


def test_linux_attestation_rejects_tampered_event(monkeypatch, tmp_path):
    monkeypatch.setenv("DEVPILOT_LINUX_AUDIT_IDENTITY_DIR", str(tmp_path / "identity"))
    event = sample_event()
    attestation = attest_event(event)

    valid, reason = verify_attestation(event, attestation)
    assert valid is True
    assert reason == "ok"

    tampered = sample_event(action="task.deleted")
    valid, reason = verify_attestation(tampered, attestation)
    assert valid is False
    assert reason in {"event_hash", "signature"}


def test_database_chain_accepts_linux_signed_events_and_detects_tampering(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("DEVPILOT_LINUX_AUDIT_IDENTITY_DIR", str(tmp_path / "identity"))

    def local_attest(**kwargs):
        payload = {
            "previous_hash": kwargs["previous_hash"],
            "workspace_id": kwargs["workspace_id"],
            "project_id": kwargs["project_id"] or "",
            "task_id": kwargs["task_id"] or "",
            "run_id": "",
            "actor": kwargs["actor"],
            "action": kwargs["action"],
            "outcome": kwargs["outcome"],
            "details": kwargs["details"],
        }
        return attest_event(payload), None

    monkeypatch.setattr(audit_service, "_attest", local_attest)

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Audit", slug="audit")
        db.add(workspace)
        db.flush()

        audit_service.record(
            db,
            workspace_id=workspace.id,
            actor="user@example.com",
            action="project.created",
            details={"slug": "alpha"},
        )
        db.flush()
        audit_service.record(
            db,
            workspace_id=workspace.id,
            actor="user@example.com",
            action="task.executed",
            details={"exit_code": 0},
        )
        db.commit()

        events = db.scalars(
            select(AuditEvent).order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        ).all()
        result = audit_service.verify_chain(events)
        assert result["valid"] is True
        assert result["events_checked"] == 2
        assert result["linux_signed_events"] == 2
        assert result["legacy_or_unsigned_events"] == 0

        second = events[1]
        stored = json.loads(second.details)
        stored["exit_code"] = 99
        second.details = json.dumps(stored, sort_keys=True, separators=(",", ":"))
        db.commit()

        result = audit_service.verify_chain(events)
        assert result["valid"] is False
        assert result["invalid_events"]
