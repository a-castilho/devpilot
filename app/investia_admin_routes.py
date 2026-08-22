from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.investia_models import (
    InvestiaCostCategory,
    InvestiaCostStatus,
    InvestiaDistributionSnapshot,
    InvestiaDistributionStatus,
    InvestiaProjectConfig,
    InvestiaProjectCost,
    InvestiaProjectStatus,
)
from app.models import Project, Workspace
from app.security import require_super_admin
from app.services.audit import record
from app.services.investia_finance import calculate_distribution, money, percentage


router = APIRouter(
    prefix="/api/admin/investia",
    tags=["Investia Admin"],
    dependencies=[Depends(require_super_admin)],
)


class InvestiaProjectCreate(BaseModel):
    external_project_key: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    funding_target: Decimal = Field(gt=0)
    minimum_funding: Decimal = Field(default=Decimal("0"), ge=0)
    maximum_funding: Decimal = Field(gt=0)
    minimum_investment: Decimal = Field(default=Decimal("1"), gt=0)
    maximum_investment_per_user: Decimal | None = Field(default=None, gt=0)
    investor_share_percentage: Decimal = Field(ge=0, le=100)
    status: InvestiaProjectStatus = InvestiaProjectStatus.draft
    public_enabled: bool = False
    notes: str = ""


class InvestiaProjectUpdate(BaseModel):
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    funding_target: Decimal | None = Field(default=None, gt=0)
    minimum_funding: Decimal | None = Field(default=None, ge=0)
    maximum_funding: Decimal | None = Field(default=None, gt=0)
    minimum_investment: Decimal | None = Field(default=None, gt=0)
    maximum_investment_per_user: Decimal | None = Field(default=None, gt=0)
    investor_share_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    status: InvestiaProjectStatus | None = None
    public_enabled: bool | None = None
    notes: str | None = None


class InvestiaCostCreate(BaseModel):
    category: InvestiaCostCategory
    description: str = Field(min_length=1, max_length=240)
    amount: Decimal = Field(gt=0)
    receipt_reference: str = Field(default="", max_length=500)


class DistributionPreviewRequest(BaseModel):
    gross_result: Decimal = Field(ge=0)
    total_captured: Decimal = Field(gt=0)
    investment_amount: Decimal | None = Field(default=None, ge=0)


class DistributionCreateRequest(DistributionPreviewRequest):
    reference_period: str = Field(min_length=1, max_length=40)


def _workspace(db: Session) -> Workspace:
    item = db.scalar(select(Workspace).where(Workspace.slug == "default"))
    if not item:
        item = Workspace(name="DevPilot", slug="default")
        db.add(item)
        db.flush()
    return item


def _project(db: Session, workspace_id: str, project_id: str) -> Project:
    item = db.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
    )
    if not item:
        raise HTTPException(404, "Project not found")
    return item


def _config(db: Session, workspace_id: str, project_id: str) -> InvestiaProjectConfig:
    item = db.scalar(
        select(InvestiaProjectConfig).where(
            InvestiaProjectConfig.workspace_id == workspace_id,
            InvestiaProjectConfig.project_id == project_id,
        )
    )
    if not item:
        raise HTTPException(404, "Investia configuration not found for project")
    return item


def _approved_cost_total(db: Session, config_id: str) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(InvestiaProjectCost.amount), 0)).where(
            InvestiaProjectCost.investia_project_id == config_id,
            InvestiaProjectCost.status == InvestiaCostStatus.approved,
        )
    )
    return money(value or 0)


def _config_view(db: Session, config: InvestiaProjectConfig, project: Project) -> dict:
    return {
        "id": config.id,
        "project_id": project.id,
        "project_name": project.name,
        "project_slug": project.slug,
        "repository_url": project.repository_url,
        "external_project_key": config.external_project_key,
        "currency": config.currency,
        "funding_target": config.funding_target,
        "minimum_funding": config.minimum_funding,
        "maximum_funding": config.maximum_funding,
        "minimum_investment": config.minimum_investment,
        "maximum_investment_per_user": config.maximum_investment_per_user,
        "investor_share_percentage": config.investor_share_percentage,
        "status": config.status,
        "public_enabled": config.public_enabled,
        "approved_costs": _approved_cost_total(db, config.id),
        "notes": config.notes,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


def _validate_funding(config: InvestiaProjectConfig) -> None:
    if config.minimum_funding > config.maximum_funding:
        raise HTTPException(422, "minimum_funding cannot exceed maximum_funding")
    if config.funding_target > config.maximum_funding:
        raise HTTPException(422, "funding_target cannot exceed maximum_funding")
    if config.maximum_investment_per_user is not None:
        if config.maximum_investment_per_user < config.minimum_investment:
            raise HTTPException(
                422,
                "maximum_investment_per_user cannot be lower than minimum_investment",
            )


@router.get("/projects")
def list_investia_projects(db: Session = Depends(get_db)):
    ws = _workspace(db)
    rows = db.execute(
        select(InvestiaProjectConfig, Project)
        .join(Project, Project.id == InvestiaProjectConfig.project_id)
        .where(InvestiaProjectConfig.workspace_id == ws.id)
        .order_by(InvestiaProjectConfig.created_at.desc())
    ).all()
    return [_config_view(db, config, project) for config, project in rows]


@router.post("/projects/{project_id}", status_code=201)
def configure_project(
    project_id: str,
    payload: InvestiaProjectCreate,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    project = _project(db, ws.id, project_id)
    existing = db.scalar(
        select(InvestiaProjectConfig).where(
            InvestiaProjectConfig.workspace_id == ws.id,
            InvestiaProjectConfig.project_id == project.id,
        )
    )
    if existing:
        raise HTTPException(409, "Project is already configured for Investia")

    duplicate_key = db.scalar(
        select(InvestiaProjectConfig.id).where(
            InvestiaProjectConfig.workspace_id == ws.id,
            InvestiaProjectConfig.external_project_key == payload.external_project_key,
        )
    )
    if duplicate_key:
        raise HTTPException(409, "external_project_key already exists")

    config = InvestiaProjectConfig(
        workspace_id=ws.id,
        project_id=project.id,
        external_project_key=payload.external_project_key.strip(),
        currency=payload.currency.upper(),
        funding_target=money(payload.funding_target),
        minimum_funding=money(payload.minimum_funding),
        maximum_funding=money(payload.maximum_funding),
        minimum_investment=money(payload.minimum_investment),
        maximum_investment_per_user=(
            money(payload.maximum_investment_per_user)
            if payload.maximum_investment_per_user is not None
            else None
        ),
        investor_share_percentage=percentage(payload.investor_share_percentage),
        status=payload.status,
        public_enabled=payload.public_enabled,
        notes=payload.notes,
    )
    _validate_funding(config)
    db.add(config)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        actor=actor,
        action="investia.project.configured",
        details={
            "investia_project_id": config.id,
            "external_project_key": config.external_project_key,
            "funding_target": str(config.funding_target),
            "investor_share_percentage": str(config.investor_share_percentage),
        },
    )
    db.commit()
    return _config_view(db, config, project)


@router.patch("/projects/{project_id}")
def update_project_config(
    project_id: str,
    payload: InvestiaProjectUpdate,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    project = _project(db, ws.id, project_id)
    config = _config(db, ws.id, project.id)
    values = payload.model_dump(exclude_unset=True)
    changed: list[str] = []

    money_fields = {
        "funding_target",
        "minimum_funding",
        "maximum_funding",
        "minimum_investment",
        "maximum_investment_per_user",
    }
    for key, value in values.items():
        if key in money_fields and value is not None:
            value = money(value)
        elif key == "investor_share_percentage" and value is not None:
            value = percentage(value)
        elif key == "currency" and value is not None:
            value = value.upper()
        setattr(config, key, value)
        changed.append(key)

    _validate_funding(config)
    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        actor=actor,
        action="investia.project.updated",
        details={"investia_project_id": config.id, "fields": sorted(changed)},
    )
    db.commit()
    return _config_view(db, config, project)


@router.get("/projects/{project_id}/costs")
def list_costs(project_id: str, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project(db, ws.id, project_id)
    config = _config(db, ws.id, project_id)
    return db.scalars(
        select(InvestiaProjectCost)
        .where(InvestiaProjectCost.investia_project_id == config.id)
        .order_by(InvestiaProjectCost.created_at.desc())
    ).all()


@router.post("/projects/{project_id}/costs", status_code=201)
def create_cost(
    project_id: str,
    payload: InvestiaCostCreate,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    project = _project(db, ws.id, project_id)
    config = _config(db, ws.id, project.id)
    item = InvestiaProjectCost(
        workspace_id=ws.id,
        investia_project_id=config.id,
        category=payload.category,
        description=payload.description.strip(),
        amount=money(payload.amount),
        receipt_reference=payload.receipt_reference.strip(),
        status=InvestiaCostStatus.pending,
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        actor=actor,
        action="investia.cost.created",
        details={
            "cost_id": item.id,
            "category": item.category.value,
            "amount": str(item.amount),
        },
    )
    db.commit()
    return item


@router.post("/costs/{cost_id}/approve")
def approve_cost(
    cost_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    item = db.scalar(
        select(InvestiaProjectCost).where(
            InvestiaProjectCost.id == cost_id,
            InvestiaProjectCost.workspace_id == ws.id,
        )
    )
    if not item:
        raise HTTPException(404, "Cost not found")
    if item.status is InvestiaCostStatus.rejected:
        raise HTTPException(409, "Rejected cost cannot be approved")
    item.status = InvestiaCostStatus.approved
    item.approved_by = actor
    item.approved_at = datetime.now(timezone.utc)
    config = db.get(InvestiaProjectConfig, item.investia_project_id)
    record(
        db,
        workspace_id=ws.id,
        project_id=config.project_id if config else None,
        actor=actor,
        action="investia.cost.approved",
        details={"cost_id": item.id, "amount": str(item.amount)},
    )
    db.commit()
    return item


@router.post("/costs/{cost_id}/reject")
def reject_cost(
    cost_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    item = db.scalar(
        select(InvestiaProjectCost).where(
            InvestiaProjectCost.id == cost_id,
            InvestiaProjectCost.workspace_id == ws.id,
        )
    )
    if not item:
        raise HTTPException(404, "Cost not found")
    item.status = InvestiaCostStatus.rejected
    item.approved_by = None
    item.approved_at = None
    config = db.get(InvestiaProjectConfig, item.investia_project_id)
    record(
        db,
        workspace_id=ws.id,
        project_id=config.project_id if config else None,
        actor=actor,
        action="investia.cost.rejected",
        details={"cost_id": item.id, "amount": str(item.amount)},
    )
    db.commit()
    return item


@router.post("/projects/{project_id}/distribution-preview")
def distribution_preview(
    project_id: str,
    payload: DistributionPreviewRequest,
    db: Session = Depends(get_db),
):
    ws = _workspace(db)
    project = _project(db, ws.id, project_id)
    config = _config(db, ws.id, project.id)
    approved_costs = _approved_cost_total(db, config.id)
    try:
        preview = calculate_distribution(
            gross_result=payload.gross_result,
            approved_costs=approved_costs,
            investor_share_percentage=config.investor_share_percentage,
            total_captured=payload.total_captured,
            investment_amount=payload.investment_amount,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {
        "project_id": project.id,
        "project_name": project.name,
        "cost_basis": "approved_only",
        **preview.as_dict(),
    }


@router.post("/projects/{project_id}/distributions", status_code=201)
def create_distribution_snapshot(
    project_id: str,
    payload: DistributionCreateRequest,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    project = _project(db, ws.id, project_id)
    config = _config(db, ws.id, project.id)
    approved_costs = _approved_cost_total(db, config.id)
    try:
        preview = calculate_distribution(
            gross_result=payload.gross_result,
            approved_costs=approved_costs,
            investor_share_percentage=config.investor_share_percentage,
            total_captured=payload.total_captured,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    item = InvestiaDistributionSnapshot(
        workspace_id=ws.id,
        investia_project_id=config.id,
        reference_period=payload.reference_period,
        gross_result=preview.gross_result,
        approved_costs=preview.approved_costs,
        net_result=preview.net_result,
        investor_share_percentage=preview.investor_share_percentage,
        distributable_pool=preview.distributable_pool,
        total_captured=preview.total_captured,
        status=InvestiaDistributionStatus.draft,
    )
    db.add(item)
    db.flush()
    record(
        db,
        workspace_id=ws.id,
        project_id=project.id,
        actor=actor,
        action="investia.distribution.created",
        details={
            "distribution_id": item.id,
            "reference_period": item.reference_period,
            "gross_result": str(item.gross_result),
            "approved_costs": str(item.approved_costs),
            "net_result": str(item.net_result),
            "distributable_pool": str(item.distributable_pool),
        },
    )
    db.commit()
    return item


@router.post("/distributions/{distribution_id}/approve")
def approve_distribution(
    distribution_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_super_admin),
):
    ws = _workspace(db)
    item = db.scalar(
        select(InvestiaDistributionSnapshot).where(
            InvestiaDistributionSnapshot.id == distribution_id,
            InvestiaDistributionSnapshot.workspace_id == ws.id,
        )
    )
    if not item:
        raise HTTPException(404, "Distribution not found")
    if item.status is not InvestiaDistributionStatus.draft:
        raise HTTPException(409, "Only draft distributions can be approved")
    item.status = InvestiaDistributionStatus.approved
    item.approved_by = actor
    item.approved_at = datetime.now(timezone.utc)
    config = db.get(InvestiaProjectConfig, item.investia_project_id)
    record(
        db,
        workspace_id=ws.id,
        project_id=config.project_id if config else None,
        actor=actor,
        action="investia.distribution.approved",
        details={"distribution_id": item.id, "distributable_pool": str(item.distributable_pool)},
    )
    db.commit()
    return item


@router.get("/projects/{project_id}/distributions")
def list_distributions(project_id: str, db: Session = Depends(get_db)):
    ws = _workspace(db)
    _project(db, ws.id, project_id)
    config = _config(db, ws.id, project_id)
    return db.scalars(
        select(InvestiaDistributionSnapshot)
        .where(InvestiaDistributionSnapshot.investia_project_id == config.id)
        .order_by(InvestiaDistributionSnapshot.created_at.desc())
    ).all()
