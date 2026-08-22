from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.investia_models import InvestiaCostStatus, InvestiaProjectConfig, InvestiaProjectCost
from app.models import Project, Workspace
from app.services.investia_finance import money


router = APIRouter(prefix="/api/investia", tags=["Investia Catalog"])


def _workspace(db: Session) -> Workspace | None:
    return db.scalar(select(Workspace).where(Workspace.slug == "default"))


def _cost_total(db: Session, config_id: str) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(InvestiaProjectCost.amount), 0)).where(
            InvestiaProjectCost.investia_project_id == config_id,
            InvestiaProjectCost.status == InvestiaCostStatus.approved,
        )
    )
    return money(value or 0)


def _cost_breakdown(db: Session, config_id: str) -> list[dict]:
    rows = db.execute(
        select(InvestiaProjectCost.category, func.sum(InvestiaProjectCost.amount))
        .where(
            InvestiaProjectCost.investia_project_id == config_id,
            InvestiaProjectCost.status == InvestiaCostStatus.approved,
        )
        .group_by(InvestiaProjectCost.category)
        .order_by(InvestiaProjectCost.category)
    ).all()
    return [
        {"category": category.value, "amount": money(amount or 0)}
        for category, amount in rows
    ]


def _public_view(db: Session, config: InvestiaProjectConfig, project: Project) -> dict:
    return {
        "project_key": config.external_project_key,
        "name": project.name,
        "slug": project.slug,
        "description": project.description,
        "currency": config.currency,
        "funding_target": config.funding_target,
        "minimum_funding": config.minimum_funding,
        "maximum_funding": config.maximum_funding,
        "minimum_investment": config.minimum_investment,
        "maximum_investment_per_user": config.maximum_investment_per_user,
        "investor_share_percentage": config.investor_share_percentage,
        "status": config.status,
        "approved_costs": _cost_total(db, config.id),
        "approved_cost_breakdown": _cost_breakdown(db, config.id),
        "updated_at": config.updated_at,
    }


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)):
    ws = _workspace(db)
    if not ws:
        return []
    rows = db.execute(
        select(InvestiaProjectConfig, Project)
        .join(Project, Project.id == InvestiaProjectConfig.project_id)
        .where(
            InvestiaProjectConfig.workspace_id == ws.id,
            InvestiaProjectConfig.public_enabled.is_(True),
        )
        .order_by(InvestiaProjectConfig.created_at.desc())
    ).all()
    return [_public_view(db, config, project) for config, project in rows]


@router.get("/catalog/{project_key}")
def catalog_project(project_key: str, db: Session = Depends(get_db)):
    ws = _workspace(db)
    if not ws:
        raise HTTPException(404, "Investia project not found")
    row = db.execute(
        select(InvestiaProjectConfig, Project)
        .join(Project, Project.id == InvestiaProjectConfig.project_id)
        .where(
            InvestiaProjectConfig.workspace_id == ws.id,
            InvestiaProjectConfig.external_project_key == project_key,
            InvestiaProjectConfig.public_enabled.is_(True),
        )
    ).first()
    if not row:
        raise HTTPException(404, "Investia project not found")
    config, project = row
    return _public_view(db, config, project)
