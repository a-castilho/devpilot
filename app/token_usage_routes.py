from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.cost_models import AIBudget, AIUsageCost
from app.db import get_db
from app.models import Project, TokenUsage, User, UserProfile
from app.security import Principal, require_access, require_super_admin, session_principal
from app.services.ai_costs import (
    PRICING_VERSION,
    backfill_cost_ledger,
    budget_status,
    microusd_to_usd,
    usd_to_microusd,
)
from app.services.audit import record
from app.services.token_usage import serialize_usage


router = APIRouter(prefix="/api/token-usage", dependencies=[Depends(require_access)], tags=["token-usage"])


class BudgetPayload(BaseModel):
    scope_type: Literal["workspace", "project", "user"] = "workspace"
    scope_id: str = ""
    daily_limit_usd: float = Field(default=0, ge=0, le=1_000_000)
    monthly_limit_usd: float = Field(default=0, ge=0, le=10_000_000)
    warning_percent: int = Field(default=80, ge=1, le=100)
    hard_stop: bool = False


@router.get("/me")
def my_token_usage(
    limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(session_principal),
    db: Session = Depends(get_db),
):
    items = db.scalars(
        select(TokenUsage)
        .where(
            TokenUsage.workspace_id == principal.workspace_id,
            TokenUsage.user_id == principal.user_id,
        )
        .order_by(TokenUsage.created_at.desc())
        .limit(limit)
    ).all()
    return [serialize_usage(item) for item in items]


def _identity_maps(db: Session, user_ids: set[str]) -> tuple[dict[str, User], dict[str, UserProfile]]:
    if not user_ids:
        return {}, {}
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    profiles = db.scalars(select(UserProfile).where(UserProfile.user_id.in_(user_ids))).all()
    return ({item.id: item for item in users}, {item.user_id: item for item in profiles})


def _user_label(user: User | None, profile: UserProfile | None) -> str:
    if profile and profile.full_name:
        return profile.full_name
    if user:
        return user.email
    return "Sistema / legado"


def _budget_payload(item: AIBudget, status: dict | None = None) -> dict:
    result = {
        "id": item.id,
        "scope_type": item.scope_type,
        "scope_id": item.scope_id,
        "daily_limit_usd": microusd_to_usd(item.daily_limit_microusd),
        "monthly_limit_usd": microusd_to_usd(item.monthly_limit_microusd),
        "warning_percent": item.warning_percent,
        "hard_stop": item.hard_stop,
    }
    if status:
        result.update(
            {
                "daily_spent_usd": microusd_to_usd(status["daily_spent_microusd"]),
                "monthly_spent_usd": microusd_to_usd(status["monthly_spent_microusd"]),
                "daily_ratio": status["daily_ratio"],
                "monthly_ratio": status["monthly_ratio"],
                "warning": status["warning"],
                "blocked": status["blocked"],
            }
        )
    return result


def _cost_cases():
    billed = case((AIUsageCost.pricing_status == "priced", AIUsageCost.cost_microusd), else_=0)
    reference = case((AIUsageCost.pricing_status == "reference", AIUsageCost.cost_microusd), else_=0)
    unpriced = case((AIUsageCost.pricing_status == "unpriced", 1), else_=0)
    reference_events = case((AIUsageCost.pricing_status == "reference", 1), else_=0)
    priced_events = case((AIUsageCost.pricing_status == "priced", 1), else_=0)
    return billed, reference, unpriced, reference_events, priced_events


@router.get("/admin/summary")
def admin_token_summary(
    days: int = Query(30, ge=1, le=365),
    principal: Principal = Depends(session_principal),
    _: str = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    filters = (
        TokenUsage.workspace_id == principal.workspace_id,
        TokenUsage.created_at >= since,
    )

    aggregate_rows = db.execute(
        select(
            TokenUsage.user_id,
            func.sum(TokenUsage.input_tokens),
            func.sum(TokenUsage.cached_input_tokens),
            func.sum(TokenUsage.output_tokens),
            func.sum(TokenUsage.total_tokens),
            func.count(TokenUsage.id),
            func.max(TokenUsage.created_at),
        )
        .where(*filters)
        .group_by(TokenUsage.user_id)
    ).all()

    user_ids = {str(row[0]) for row in aggregate_rows if row[0]}
    users, profiles = _identity_maps(db, user_ids)
    by_user: list[dict] = []
    for row in aggregate_rows:
        user_id = str(row[0]) if row[0] else None
        user = users.get(user_id or "")
        profile = profiles.get(user_id or "")
        by_user.append(
            {
                "user_id": user_id,
                "email": user.email if user else None,
                "name": _user_label(user, profile),
                "input_tokens": int(row[1] or 0),
                "cached_input_tokens": int(row[2] or 0),
                "output_tokens": int(row[3] or 0),
                "total_tokens": int(row[4] or 0),
                "events": int(row[5] or 0),
                "last_used_at": row[6],
            }
        )
    by_user.sort(key=lambda item: item["total_tokens"], reverse=True)

    recent_items = db.scalars(
        select(TokenUsage)
        .where(*filters)
        .order_by(TokenUsage.created_at.desc())
        .limit(100)
    ).all()
    recent_user_ids = {item.user_id for item in recent_items if item.user_id}
    if recent_user_ids - user_ids:
        extra_users, extra_profiles = _identity_maps(db, set(recent_user_ids - user_ids))
        users.update(extra_users)
        profiles.update(extra_profiles)

    recent: list[dict] = []
    for item in recent_items:
        payload = serialize_usage(item)
        user = users.get(item.user_id or "")
        profile = profiles.get(item.user_id or "")
        payload["user_email"] = user.email if user else None
        payload["user_name"] = _user_label(user, profile)
        recent.append(payload)

    totals = {
        "input_tokens": sum(item["input_tokens"] for item in by_user),
        "cached_input_tokens": sum(item["cached_input_tokens"] for item in by_user),
        "output_tokens": sum(item["output_tokens"] for item in by_user),
        "total_tokens": sum(item["total_tokens"] for item in by_user),
        "events": sum(item["events"] for item in by_user),
        "users": sum(1 for item in by_user if item["user_id"]),
    }
    return {
        "period_days": days,
        "since": since,
        "totals": totals,
        "by_user": by_user,
        "recent": recent,
    }


@router.get("/admin/cost-summary")
def admin_cost_summary(
    days: int = Query(30, ge=1, le=365),
    principal: Principal = Depends(session_principal),
    _: str = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    backfilled = backfill_cost_ledger(db, principal.workspace_id)
    if backfilled:
        # Backfill is idempotent and must survive this read request; get_db does
        # not auto-commit sessions.
        db.commit()

    since = datetime.now(timezone.utc) - timedelta(days=days)
    filters = (
        AIUsageCost.workspace_id == principal.workspace_id,
        AIUsageCost.created_at >= since,
    )
    billed_case, reference_case, unpriced_case, reference_event_case, priced_event_case = _cost_cases()

    totals_row = db.execute(
        select(
            func.coalesce(func.sum(billed_case), 0),
            func.coalesce(func.sum(reference_case), 0),
            func.count(AIUsageCost.id),
            func.coalesce(func.sum(priced_event_case), 0),
            func.coalesce(func.sum(reference_event_case), 0),
            func.coalesce(func.sum(unpriced_case), 0),
        ).where(*filters)
    ).one()
    total_cost_microusd = int(totals_row[0] or 0)
    reference_cost_microusd = int(totals_row[1] or 0)
    total_events = int(totals_row[2] or 0)
    priced_events = int(totals_row[3] or 0)
    reference_events = int(totals_row[4] or 0)
    unpriced_events = int(totals_row[5] or 0)

    project_rows = db.execute(
        select(
            AIUsageCost.project_id,
            func.coalesce(func.sum(billed_case), 0),
            func.coalesce(func.sum(reference_case), 0),
            func.count(AIUsageCost.id),
            func.coalesce(func.sum(unpriced_case), 0),
            func.max(AIUsageCost.created_at),
        )
        .where(*filters)
        .group_by(AIUsageCost.project_id)
    ).all()
    project_ids = {str(row[0]) for row in project_rows if row[0]}
    projects = {
        item.id: item
        for item in db.scalars(
            select(Project).where(
                Project.workspace_id == principal.workspace_id,
                Project.id.in_(project_ids),
            )
        ).all()
    } if project_ids else {}
    by_project = [
        {
            "project_id": str(row[0]) if row[0] else None,
            "project_name": projects.get(str(row[0])).name if row[0] and projects.get(str(row[0])) else "Sem projeto",
            "cost_usd": microusd_to_usd(row[1]),
            "reference_cost_usd": microusd_to_usd(row[2]),
            "events": int(row[3] or 0),
            "unpriced_events": int(row[4] or 0),
            "last_used_at": row[5],
        }
        for row in project_rows
    ]
    by_project.sort(key=lambda item: (item["cost_usd"], item["reference_cost_usd"]), reverse=True)

    model_rows = db.execute(
        select(
            AIUsageCost.provider,
            AIUsageCost.model,
            func.coalesce(func.sum(billed_case), 0),
            func.coalesce(func.sum(reference_case), 0),
            func.count(AIUsageCost.id),
            func.coalesce(func.sum(unpriced_case), 0),
        )
        .where(*filters)
        .group_by(AIUsageCost.provider, AIUsageCost.model)
    ).all()
    by_model = [
        {
            "provider": str(row[0]),
            "model": str(row[1]),
            "cost_usd": microusd_to_usd(row[2]),
            "reference_cost_usd": microusd_to_usd(row[3]),
            "events": int(row[4] or 0),
            "unpriced_events": int(row[5] or 0),
        }
        for row in model_rows
    ]
    by_model.sort(key=lambda item: (item["cost_usd"], item["reference_cost_usd"]), reverse=True)

    user_rows = db.execute(
        select(
            AIUsageCost.user_id,
            func.coalesce(func.sum(billed_case), 0),
            func.coalesce(func.sum(reference_case), 0),
            func.count(AIUsageCost.id),
            func.coalesce(func.sum(unpriced_case), 0),
        )
        .where(*filters)
        .group_by(AIUsageCost.user_id)
    ).all()
    cost_user_ids = {str(row[0]) for row in user_rows if row[0]}
    cost_users, cost_profiles = _identity_maps(db, cost_user_ids)
    by_user = [
        {
            "user_id": str(row[0]) if row[0] else None,
            "name": _user_label(
                cost_users.get(str(row[0]) if row[0] else ""),
                cost_profiles.get(str(row[0]) if row[0] else ""),
            ),
            "cost_usd": microusd_to_usd(row[1]),
            "reference_cost_usd": microusd_to_usd(row[2]),
            "events": int(row[3] or 0),
            "unpriced_events": int(row[4] or 0),
        }
        for row in user_rows
    ]
    by_user.sort(key=lambda item: (item["cost_usd"], item["reference_cost_usd"]), reverse=True)

    recent_items = db.scalars(
        select(AIUsageCost)
        .where(*filters)
        .order_by(AIUsageCost.created_at.desc())
        .limit(50)
    ).all()
    recent_user_ids = {item.user_id for item in recent_items if item.user_id}
    recent_project_ids = {item.project_id for item in recent_items if item.project_id}
    recent_users, recent_profiles = _identity_maps(db, set(recent_user_ids))
    recent_projects = {
        item.id: item
        for item in db.scalars(
            select(Project).where(
                Project.workspace_id == principal.workspace_id,
                Project.id.in_(recent_project_ids),
            )
        ).all()
    } if recent_project_ids else {}
    recent = [
        {
            "id": item.id,
            "user_name": _user_label(
                recent_users.get(item.user_id or ""),
                recent_profiles.get(item.user_id or ""),
            ),
            "project_name": recent_projects.get(item.project_id).name if item.project_id and recent_projects.get(item.project_id) else "Sem projeto",
            "provider": item.provider,
            "model": item.model,
            "operation": item.operation,
            "cost_usd": microusd_to_usd(item.cost_microusd),
            "pricing_status": item.pricing_status,
            "pricing_version": item.pricing_version,
            "billable_unit": item.billable_unit,
            "billable_quantity": item.billable_quantity,
            "created_at": item.created_at,
        }
        for item in recent_items
    ]

    budgets = db.scalars(
        select(AIBudget)
        .where(AIBudget.workspace_id == principal.workspace_id)
        .order_by(AIBudget.scope_type, AIBudget.scope_id)
    ).all()
    budget_rows: list[dict] = []
    for budget in budgets:
        kwargs: dict[str, str] = {}
        if budget.scope_type == "user":
            kwargs["user_id"] = budget.scope_id
        elif budget.scope_type == "project":
            kwargs["project_id"] = budget.scope_id
        statuses = budget_status(db, workspace_id=principal.workspace_id, **kwargs)
        status = next((item for item in statuses if item["id"] == budget.id), None)
        budget_rows.append(_budget_payload(budget, status))

    fx_rate = max(0.0, float(get_settings().usd_brl_rate or 0))
    cost_usd = microusd_to_usd(total_cost_microusd)
    reference_cost_usd = microusd_to_usd(reference_cost_microusd)
    coverage_denominator = priced_events + unpriced_events
    return {
        "period_days": days,
        "since": since,
        "pricing_version": PRICING_VERSION,
        "backfilled_events": backfilled,
        "totals": {
            "cost_usd": cost_usd,
            "cost_brl": round(cost_usd * fx_rate, 4) if fx_rate > 0 else None,
            "reference_cost_usd": reference_cost_usd,
            "events": total_events,
            "priced_events": priced_events,
            "reference_events": reference_events,
            "unpriced_events": unpriced_events,
            "coverage_percent": (
                round((priced_events / coverage_denominator) * 100, 1)
                if coverage_denominator
                else 100.0
            ),
        },
        "usd_brl_rate": fx_rate or None,
        "by_project": by_project,
        "by_model": by_model,
        "by_user": by_user,
        "recent": recent,
        "budgets": budget_rows,
    }


@router.get("/admin/budgets")
def admin_budgets(
    principal: Principal = Depends(session_principal),
    _: str = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    items = db.scalars(
        select(AIBudget)
        .where(AIBudget.workspace_id == principal.workspace_id)
        .order_by(AIBudget.scope_type, AIBudget.scope_id)
    ).all()
    return [_budget_payload(item) for item in items]


@router.put("/admin/budgets")
def upsert_admin_budget(
    payload: BudgetPayload,
    principal: Principal = Depends(session_principal),
    _: str = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    scope_id = payload.scope_id.strip()
    if payload.scope_type == "workspace":
        scope_id = ""
    elif not scope_id:
        raise HTTPException(422, "Informe o usuário ou projeto do orçamento")
    elif payload.scope_type == "project":
        exists = db.scalar(
            select(Project.id).where(
                Project.id == scope_id,
                Project.workspace_id == principal.workspace_id,
            )
        )
        if not exists:
            raise HTTPException(404, "Projeto não encontrado")
    elif payload.scope_type == "user":
        exists = db.scalar(
            select(User.id).where(
                User.id == scope_id,
                User.workspace_id == principal.workspace_id,
            )
        )
        if not exists:
            raise HTTPException(404, "Usuário não encontrado")

    item = db.scalar(
        select(AIBudget).where(
            AIBudget.workspace_id == principal.workspace_id,
            AIBudget.scope_type == payload.scope_type,
            AIBudget.scope_id == scope_id,
        )
    )
    if not item:
        item = AIBudget(
            workspace_id=principal.workspace_id,
            scope_type=payload.scope_type,
            scope_id=scope_id,
        )
        db.add(item)

    item.daily_limit_microusd = usd_to_microusd(payload.daily_limit_usd)
    item.monthly_limit_microusd = usd_to_microusd(payload.monthly_limit_usd)
    item.warning_percent = payload.warning_percent
    item.hard_stop = payload.hard_stop
    db.flush()
    record(
        db,
        workspace_id=principal.workspace_id,
        actor=f"user:{principal.user_id}",
        action="ai.budget.updated",
        details={
            "budget_id": item.id,
            "scope_type": item.scope_type,
            "scope_id": item.scope_id,
            "daily_limit_microusd": item.daily_limit_microusd,
            "monthly_limit_microusd": item.monthly_limit_microusd,
            "warning_percent": item.warning_percent,
            "hard_stop": item.hard_stop,
        },
    )
    db.commit()
    return _budget_payload(item)
