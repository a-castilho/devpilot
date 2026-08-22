import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.cost_models import AIBudget, AIUsageCost
from app.db import Base
from app.models import AuditEvent, TokenUsage, User, Workspace
from app.services.ai_costs import (
    budget_block_reason,
    calculate_token_cost_microusd,
    record_unpriced_cost,
    usd_to_microusd,
)
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


def test_gpt_56_cost_prices_cached_tokens_separately():
    cost, status, version = calculate_token_cost_microusd(
        provider="openai",
        model="gpt-5.6",
        operation="voice.chat",
        input_tokens=1_000_000,
        cached_input_tokens=200_000,
        output_tokens=100_000,
    )
    # 800k * $5/M + 200k * $0.50/M + 100k * $30/M = $7.10
    assert cost == 7_100_000
    assert status == "priced"
    assert version == "2026-08-22"


def test_unknown_model_stays_visible_but_unpriced():
    cost, status, _ = calculate_token_cost_microusd(
        provider="unknown",
        model="future-model",
        operation="test",
        input_tokens=10,
        cached_input_tokens=0,
        output_tokens=2,
    )
    assert cost == 0
    assert status == "unpriced"


def test_record_usage_persists_usage_cost_and_audit_event():
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
            model="gpt-5.6",
            operation="test.operation",
            counts=TokenCounts(input_tokens=1000, output_tokens=100, total_tokens=1100),
        )
        db.commit()

        assert usage is not None
        stored = db.scalar(select(TokenUsage).where(TokenUsage.id == usage.id))
        cost = db.scalar(select(AIUsageCost).where(AIUsageCost.token_usage_id == usage.id))
        audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "tokens.consumed"))
        assert stored is not None
        assert stored.user_id == user.id
        assert stored.total_tokens == 1100
        assert cost is not None
        assert cost.pricing_status == "priced"
        assert cost.cost_microusd > 0
        assert audit is not None
        assert audit.actor == f"user:{user.id}"


def test_unpriced_external_usage_is_kept_in_financial_ledger():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="TTS", slug="tts")
        db.add(workspace)
        db.flush()
        event = record_unpriced_cost(
            db,
            workspace_id=workspace.id,
            user_id=None,
            provider="openai",
            model="gpt-4o-mini-tts",
            operation="voice.speech",
            billable_unit="characters",
            billable_quantity=320,
        )
        db.commit()
        stored = db.get(AIUsageCost, event.id)
        assert stored is not None
        assert stored.pricing_status == "unpriced"
        assert stored.billable_quantity == 320
        assert stored.cost_microusd == 0


def test_budget_hard_stop_blocks_after_priced_spend_reaches_limit():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Budget", slug="budget")
        db.add(workspace)
        db.flush()
        budget = AIBudget(
            workspace_id=workspace.id,
            scope_type="workspace",
            scope_id="",
            daily_limit_microusd=usd_to_microusd(1.0),
            monthly_limit_microusd=usd_to_microusd(10.0),
            warning_percent=80,
            hard_stop=True,
        )
        db.add(budget)
        db.flush()
        db.add(
            AIUsageCost(
                workspace_id=workspace.id,
                provider="openai",
                model="gpt-5.6",
                operation="test",
                cost_microusd=usd_to_microusd(1.0),
                pricing_status="priced",
                pricing_version="2026-08-22",
                billable_unit="tokens",
                billable_quantity=1,
                source="test",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        reason = budget_block_reason(db, workspace_id=workspace.id)
        assert reason is not None
        assert "Orçamento de IA" in reason
