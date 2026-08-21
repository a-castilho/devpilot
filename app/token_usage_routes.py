from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import TokenUsage, User, UserProfile
from app.security import Principal, require_access, require_super_admin, session_principal
from app.services.token_usage import serialize_usage


router = APIRouter(prefix="/api/token-usage", dependencies=[Depends(require_access)], tags=["token-usage"])


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
                "name": profile.full_name if profile and profile.full_name else (user.email if user else "Sistema / legado"),
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
        payload["user_name"] = (
            profile.full_name
            if profile and profile.full_name
            else (user.email if user else "Sistema / legado")
        )
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
