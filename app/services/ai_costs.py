from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.cost_models import AIBudget, AIUsageCost
from app.models import TokenUsage


PRICING_VERSION = "2026-08-22"
MICRO_USD = 1_000_000


@dataclass(frozen=True)
class TokenPrice:
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float


# Standard paid-tier prices captured from official provider pricing on 2026-08-22.
# The version is persisted with each ledger entry so historical values never change
# when a provider later updates its public price list.
_STANDARD_PRICES: dict[tuple[str, str], TokenPrice] = {
    ("openai", "gpt-5.6"): TokenPrice(5.00, 0.50, 30.00),
    ("openai", "gpt-5.6-sol"): TokenPrice(5.00, 0.50, 30.00),
    ("openai", "gpt-5.6-terra"): TokenPrice(2.00, 0.20, 12.00),
    ("openai", "gpt-5.6-luna"): TokenPrice(0.20, 0.02, 1.20),
    ("openai", "gpt-5.4"): TokenPrice(2.50, 0.25, 15.00),
    ("openai", "gpt-5"): TokenPrice(1.25, 0.125, 10.00),
    ("openai", "gpt-4.1-mini"): TokenPrice(0.40, 0.10, 1.60),
    ("openai", "gpt-4o-mini"): TokenPrice(0.15, 0.075, 0.60),
    ("openai-transcription", "gpt-4o-mini-transcribe"): TokenPrice(1.25, 1.25, 5.00),
    ("google", "gemini-3.6-flash"): TokenPrice(1.50, 0.15, 7.50),
    ("google", "gemini-3.5-flash"): TokenPrice(1.50, 0.15, 9.00),
    ("google", "gemini-2.5-flash"): TokenPrice(0.30, 0.03, 2.50),
    # Gemini 2.5 Flash bills audio input at a higher rate than text input.
    ("google-audio", "gemini-2.5-flash"): TokenPrice(1.00, 0.10, 2.50),
}


def _canonical_provider(provider: str, operation: str) -> str:
    value = str(provider or "").strip().lower()
    operation = str(operation or "").strip().lower()
    if value in {"openai", "openai-codex"}:
        if operation == "voice.transcription":
            return "openai-transcription"
        return "openai"
    if value == "google" and operation == "voice.transcription":
        return "google-audio"
    return value


def _lookup_price(provider: str, model: str, operation: str) -> TokenPrice | None:
    canonical = _canonical_provider(provider, operation)
    normalized_model = str(model or "default").strip().lower()
    exact = _STANDARD_PRICES.get((canonical, normalized_model))
    if exact:
        return exact

    candidates = sorted(
        (
            (name, price)
            for (candidate_provider, name), price in _STANDARD_PRICES.items()
            if candidate_provider == canonical
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for name, price in candidates:
        if normalized_model.startswith(f"{name}-"):
            return price
    return None


def calculate_token_cost_microusd(
    *,
    provider: str,
    model: str,
    operation: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> tuple[int, str, str]:
    price = _lookup_price(provider, model, operation)
    if price is None:
        return 0, "unpriced", PRICING_VERSION

    input_tokens = max(0, int(input_tokens or 0))
    cached_input_tokens = min(input_tokens, max(0, int(cached_input_tokens or 0)))
    output_tokens = max(0, int(output_tokens or 0))
    uncached_input = input_tokens - cached_input_tokens

    # Rates are USD per 1M tokens. Tokens × rate is therefore micro-USD.
    value_microusd = round(
        uncached_input * price.input_per_million
        + cached_input_tokens * price.cached_input_per_million
        + output_tokens * price.output_per_million
    )

    # Codex CLI may be authenticated through a ChatGPT subscription rather than
    # metered API billing. Preserve its API-equivalent value for comparison, but
    # never mix that reference amount with authoritative provider spend/budgets.
    status = "reference" if str(provider or "").strip().lower() == "openai-codex" else "priced"
    return max(0, int(value_microusd)), status, PRICING_VERSION


def record_token_cost(db: Session, usage: TokenUsage) -> AIUsageCost:
    existing = db.scalar(select(AIUsageCost).where(AIUsageCost.token_usage_id == usage.id))
    if existing:
        return existing

    cost_microusd, pricing_status, pricing_version = calculate_token_cost_microusd(
        provider=usage.provider,
        model=usage.model,
        operation=usage.operation,
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.cached_input_tokens,
        output_tokens=usage.output_tokens,
    )
    item = AIUsageCost(
        workspace_id=usage.workspace_id,
        token_usage_id=usage.id,
        user_id=usage.user_id,
        project_id=usage.project_id,
        task_id=usage.task_id,
        run_id=usage.run_id,
        provider=usage.provider,
        model=usage.model,
        operation=usage.operation,
        cost_microusd=cost_microusd,
        pricing_status=pricing_status,
        pricing_version=pricing_version,
        billable_unit="tokens",
        billable_quantity=usage.total_tokens,
        source=usage.source,
        created_at=usage.created_at,
    )
    db.add(item)
    db.flush()
    return item


def record_unpriced_cost(
    db: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    provider: str,
    model: str,
    operation: str,
    billable_unit: str,
    billable_quantity: int,
    project_id: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    source: str = "provider-no-usage",
) -> AIUsageCost:
    item = AIUsageCost(
        workspace_id=workspace_id,
        user_id=user_id,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        provider=str(provider or "unknown")[:50],
        model=str(model or "default")[:120],
        operation=str(operation or "unknown")[:80],
        cost_microusd=0,
        pricing_status="unpriced",
        pricing_version=PRICING_VERSION,
        billable_unit=str(billable_unit or "unit")[:30],
        billable_quantity=max(0, int(billable_quantity or 0)),
        source=str(source or "provider-no-usage")[:40],
    )
    db.add(item)
    db.flush()
    return item


def backfill_cost_ledger(db: Session, workspace_id: str, limit: int = 5000) -> int:
    rows = db.scalars(
        select(TokenUsage)
        .outerjoin(AIUsageCost, AIUsageCost.token_usage_id == TokenUsage.id)
        .where(TokenUsage.workspace_id == workspace_id, AIUsageCost.id.is_(None))
        .order_by(TokenUsage.created_at.asc())
        .limit(limit)
    ).all()
    for usage in rows:
        record_token_cost(db, usage)
    if rows:
        db.flush()
    return len(rows)


def _period_start(now: datetime) -> tuple[datetime, datetime]:
    current = now.astimezone(timezone.utc)
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = day_start.replace(day=1)
    return day_start, month_start


def _scope_filters(budget: AIBudget):
    if budget.scope_type == "user":
        return (AIUsageCost.user_id == budget.scope_id,)
    if budget.scope_type == "project":
        return (AIUsageCost.project_id == budget.scope_id,)
    return ()


def _spent_since(db: Session, budget: AIBudget, since: datetime) -> int:
    value = db.scalar(
        select(func.coalesce(func.sum(AIUsageCost.cost_microusd), 0)).where(
            AIUsageCost.workspace_id == budget.workspace_id,
            AIUsageCost.created_at >= since,
            AIUsageCost.pricing_status == "priced",
            *_scope_filters(budget),
        )
    )
    return int(value or 0)


def applicable_budgets(
    db: Session,
    *,
    workspace_id: str,
    user_id: str | None = None,
    project_id: str | None = None,
) -> list[AIBudget]:
    scope_predicates = [AIBudget.scope_type == "workspace"]
    if user_id:
        scope_predicates.append((AIBudget.scope_type == "user") & (AIBudget.scope_id == user_id))
    if project_id:
        scope_predicates.append((AIBudget.scope_type == "project") & (AIBudget.scope_id == project_id))
    return list(
        db.scalars(
            select(AIBudget)
            .where(AIBudget.workspace_id == workspace_id, or_(*scope_predicates))
            .order_by(AIBudget.scope_type, AIBudget.scope_id)
        ).all()
    )


def budget_status(
    db: Session,
    *,
    workspace_id: str,
    user_id: str | None = None,
    project_id: str | None = None,
    now: datetime | None = None,
) -> list[dict]:
    backfill_cost_ledger(db, workspace_id)
    day_start, month_start = _period_start(now or datetime.now(timezone.utc))
    result: list[dict] = []
    for budget in applicable_budgets(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        project_id=project_id,
    ):
        daily_spent = _spent_since(db, budget, day_start)
        monthly_spent = _spent_since(db, budget, month_start)
        daily_ratio = daily_spent / budget.daily_limit_microusd if budget.daily_limit_microusd > 0 else 0.0
        monthly_ratio = monthly_spent / budget.monthly_limit_microusd if budget.monthly_limit_microusd > 0 else 0.0
        result.append(
            {
                "id": budget.id,
                "scope_type": budget.scope_type,
                "scope_id": budget.scope_id,
                "daily_limit_microusd": budget.daily_limit_microusd,
                "monthly_limit_microusd": budget.monthly_limit_microusd,
                "daily_spent_microusd": daily_spent,
                "monthly_spent_microusd": monthly_spent,
                "daily_ratio": daily_ratio,
                "monthly_ratio": monthly_ratio,
                "warning_percent": budget.warning_percent,
                "hard_stop": budget.hard_stop,
                "warning": max(daily_ratio, monthly_ratio) >= (budget.warning_percent / 100),
                "blocked": bool(
                    budget.hard_stop
                    and (
                        (budget.daily_limit_microusd > 0 and daily_spent >= budget.daily_limit_microusd)
                        or (budget.monthly_limit_microusd > 0 and monthly_spent >= budget.monthly_limit_microusd)
                    )
                ),
            }
        )
    return result


def budget_block_reason(
    db: Session,
    *,
    workspace_id: str,
    user_id: str | None = None,
    project_id: str | None = None,
) -> str | None:
    for status in budget_status(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        project_id=project_id,
    ):
        if not status["blocked"]:
            continue
        scope = status["scope_type"]
        label = "workspace" if scope == "workspace" else "projeto" if scope == "project" else "usuário"
        return (
            f"Orçamento de IA do {label} atingido. "
            "A execução foi bloqueada para evitar gasto adicional; o Super Admin pode revisar o limite."
        )
    return None


def microusd_to_usd(value: int | None) -> float:
    return round(int(value or 0) / MICRO_USD, 6)


def usd_to_microusd(value: float | int | None) -> int:
    return max(0, round(float(value or 0) * MICRO_USD))
