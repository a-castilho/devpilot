from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.cost_models import AIBudget, AIUsageCost
from app.db import Base
from app.models import Workspace
from app.services.ai_costs import (
    budget_block_reason,
    calculate_token_cost_microusd,
    usd_to_microusd,
)


def test_codex_cost_is_reference_not_authoritative_billing():
    value, status, _ = calculate_token_cost_microusd(
        provider="openai-codex",
        model="gpt-5.6",
        operation="task.execution",
        input_tokens=1_000_000,
        cached_input_tokens=0,
        output_tokens=100_000,
    )
    assert value > 0
    assert status == "reference"


def test_reference_cost_does_not_trigger_hard_stop_budget():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        workspace = Workspace(name="Codex", slug="codex-budget")
        db.add(workspace)
        db.flush()
        db.add(
            AIBudget(
                workspace_id=workspace.id,
                scope_type="workspace",
                scope_id="",
                daily_limit_microusd=usd_to_microusd(1.0),
                monthly_limit_microusd=usd_to_microusd(1.0),
                warning_percent=80,
                hard_stop=True,
            )
        )
        db.add(
            AIUsageCost(
                workspace_id=workspace.id,
                provider="openai-codex",
                model="gpt-5.6",
                operation="task.execution",
                cost_microusd=usd_to_microusd(50.0),
                pricing_status="reference",
                pricing_version="2026-08-22",
                billable_unit="tokens",
                billable_quantity=1_000_000,
                source="provider-reported",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        assert budget_block_reason(db, workspace_id=workspace.id) is None
