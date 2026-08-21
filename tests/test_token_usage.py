import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AuditEvent, TokenUsage, User, Workspace
from app.services.token_usage import (
    TokenCounts,
    extract_codex_usage,
    record_usage,
    token_counts_from_usage,
    user_id_from_actor,
)


def test_openai_usage_normalization_keeps_cached_tokens_inside_total():
    counts = token_counts_from_usage(
        {
            "input_tokens": 120,
            "input_tokens_details": {"cached_tokens": 40},
            "output_tokens": 30,
            "total_tokens": 150,
        }
    )
    assert counts.input_tokens == 120
    assert counts.cached_input_tokens == 40
    assert counts.output_tokens == 30
    assert counts.total_tokens == 150


def test_google_usage_normalization():
    counts = token_counts_from_usage(
        {
            "promptTokenCount": 80,
            "cachedContentTokenCount": 20,
            "candidatesTokenCount": 15,
            "totalTokenCount": 95,
        }
    )
    assert counts.as_dict() == {
        "input_tokens": 80,
        "cached_input_tokens": 20,
        "output_tokens": 15,
        "total_tokens": 95,
    }


def test_codex_uses_last_completed_turn_usage():
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "abc"}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 25, "cached_input_tokens": 5, "output_tokens": 4, "total_tokens": 29}}),
        ]
    )
    counts = extract_codex_usage(stdout)
    assert counts.total_tokens == 29
    assert counts.input_tokens == 25
    assert counts.cached_input_tokens == 5
    assert counts.output_tokens == 4


def test_usage_is_not_estimated_without_provider_metadata():
    assert token_counts_from_usage(None).total_tokens == 0
    assert extract_codex_usage('{"type":"item.completed","text":"ok"}').total_tokens == 0


def test_user_id_is_resolved_only_from_user_actor():
    assert user_id_from_actor("user:abc-123") == "abc-123"
    assert user_id_from_actor("worker") is None
    assert user_id_from_actor("owner") is None


def test_record_usage_persists_usage_and_audit_event():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Tokens", slug="tokens")
        db.add(workspace)
        db.flush()
        user = User(
            workspace_id=workspace.id,
            email="tokens@example.com",
            password_hash="test",
            role="VIEWER",
            active=True,
        )
        db.add(user)
        db.flush()

        usage = record_usage(
            db,
            workspace_id=workspace.id,
            user_id=user.id,
            provider="openai",
            model="gpt-test",
            operation="test.operation",
            counts=TokenCounts(input_tokens=10, output_tokens=3, total_tokens=13),
        )
        db.commit()

        assert usage is not None
        stored = db.scalar(select(TokenUsage).where(TokenUsage.id == usage.id))
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "tokens.consumed"))
        assert stored is not None
        assert stored.user_id == user.id
        assert stored.total_tokens == 13
        assert audit is not None
        assert audit.actor == f"user:{user.id}"
