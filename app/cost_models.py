from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import uid


def now() -> datetime:
    return datetime.now(timezone.utc)


class AIUsageCost(Base):
    __tablename__ = "ai_usage_costs"
    __table_args__ = (
        UniqueConstraint("token_usage_id", name="uq_ai_usage_cost_token_usage"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    token_usage_id: Mapped[str | None] = mapped_column(ForeignKey("token_usage.id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(120), default="default", index=True)
    operation: Mapped[str] = mapped_column(String(80), index=True)
    cost_microusd: Mapped[int] = mapped_column(Integer, default=0)
    pricing_status: Mapped[str] = mapped_column(String(20), default="unpriced", index=True)
    pricing_version: Mapped[str] = mapped_column(String(40), default="")
    billable_unit: Mapped[str] = mapped_column(String(30), default="tokens")
    billable_quantity: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(40), default="provider-reported")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class AIBudget(Base):
    __tablename__ = "ai_budgets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "scope_type", "scope_id", name="uq_ai_budget_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    scope_type: Mapped[str] = mapped_column(String(20), default="workspace", index=True)
    scope_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    daily_limit_microusd: Mapped[int] = mapped_column(Integer, default=0)
    monthly_limit_microusd: Mapped[int] = mapped_column(Integer, default=0)
    warning_percent: Mapped[int] = mapped_column(Integer, default=80)
    hard_stop: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
