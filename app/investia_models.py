from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models import now, uid


class InvestiaProjectStatus(str, enum.Enum):
    draft = "draft"
    fundraising = "fundraising"
    funded = "funded"
    operating = "operating"
    distributing = "distributing"
    completed = "completed"
    paused = "paused"
    cancelled = "cancelled"


class InvestiaCostCategory(str, enum.Enum):
    infrastructure = "infrastructure"
    development = "development"
    operations = "operations"
    fees = "fees"
    taxes = "taxes"
    other = "other"


class InvestiaCostStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class InvestiaDistributionStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    paid = "paid"
    cancelled = "cancelled"


class InvestiaProjectConfig(Base):
    __tablename__ = "investia_project_configs"
    __table_args__ = (
        UniqueConstraint("workspace_id", "project_id"),
        UniqueConstraint("workspace_id", "external_project_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    external_project_key: Mapped[str] = mapped_column(String(120), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    funding_target: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    minimum_funding: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    maximum_funding: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    minimum_investment: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("1.00"))
    maximum_investment_per_user: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    investor_share_percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0.0000"))
    status: Mapped[InvestiaProjectStatus] = mapped_column(
        Enum(InvestiaProjectStatus), default=InvestiaProjectStatus.draft, index=True
    )
    public_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class InvestiaProjectCost(Base):
    __tablename__ = "investia_project_costs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    investia_project_id: Mapped[str] = mapped_column(
        ForeignKey("investia_project_configs.id"), index=True
    )
    category: Mapped[InvestiaCostCategory] = mapped_column(Enum(InvestiaCostCategory), index=True)
    description: Mapped[str] = mapped_column(String(240))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    receipt_reference: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[InvestiaCostStatus] = mapped_column(
        Enum(InvestiaCostStatus), default=InvestiaCostStatus.pending, index=True
    )
    approved_by: Mapped[str | None] = mapped_column(String(120))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class InvestiaDistributionSnapshot(Base):
    __tablename__ = "investia_distribution_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    investia_project_id: Mapped[str] = mapped_column(
        ForeignKey("investia_project_configs.id"), index=True
    )
    reference_period: Mapped[str] = mapped_column(String(40))
    gross_result: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    approved_costs: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    net_result: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    investor_share_percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    distributable_pool: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_captured: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[InvestiaDistributionStatus] = mapped_column(
        Enum(InvestiaDistributionStatus), default=InvestiaDistributionStatus.draft, index=True
    )
    approved_by: Mapped[str | None] = mapped_column(String(120))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
