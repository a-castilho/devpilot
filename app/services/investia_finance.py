from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


MONEY_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.0001")
HUNDRED = Decimal("100")


def _decimal(value: Decimal | int | str | float) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value: Decimal | int | str | float) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def percentage(value: Decimal | int | str | float) -> Decimal:
    return _decimal(value).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def _non_negative(name: str, value: Decimal) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class DistributionPreview:
    gross_result: Decimal
    approved_costs: Decimal
    net_result: Decimal
    investor_share_percentage: Decimal
    distributable_pool: Decimal
    total_captured: Decimal
    investment_amount: Decimal | None
    participation_percentage: Decimal | None
    investor_return: Decimal | None

    def as_dict(self) -> dict[str, Decimal | None]:
        return {
            "gross_result": self.gross_result,
            "approved_costs": self.approved_costs,
            "net_result": self.net_result,
            "investor_share_percentage": self.investor_share_percentage,
            "distributable_pool": self.distributable_pool,
            "total_captured": self.total_captured,
            "investment_amount": self.investment_amount,
            "participation_percentage": self.participation_percentage,
            "investor_return": self.investor_return,
        }


def calculate_participation(
    investment_amount: Decimal | int | str | float,
    total_captured: Decimal | int | str | float,
) -> Decimal:
    investment = money(investment_amount)
    captured = money(total_captured)
    _non_negative("investment_amount", investment)
    if captured <= 0:
        raise ValueError("total_captured must be greater than zero")
    if investment > captured:
        raise ValueError("investment_amount cannot exceed total_captured")
    return (investment / captured * HUNDRED).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def calculate_distribution(
    *,
    gross_result: Decimal | int | str | float,
    approved_costs: Decimal | int | str | float,
    investor_share_percentage: Decimal | int | str | float,
    total_captured: Decimal | int | str | float,
    investment_amount: Decimal | int | str | float | None = None,
) -> DistributionPreview:
    gross = money(gross_result)
    costs = money(approved_costs)
    share = percentage(investor_share_percentage)
    captured = money(total_captured)

    _non_negative("gross_result", gross)
    _non_negative("approved_costs", costs)
    _non_negative("total_captured", captured)
    if share < 0 or share > HUNDRED:
        raise ValueError("investor_share_percentage must be between 0 and 100")

    net = money(max(gross - costs, Decimal("0")))
    pool = money(net * (share / HUNDRED))

    investment: Decimal | None = None
    participation: Decimal | None = None
    investor_return: Decimal | None = None
    if investment_amount is not None:
        investment = money(investment_amount)
        participation = calculate_participation(investment, captured)
        investor_return = money(pool * (participation / HUNDRED))

    return DistributionPreview(
        gross_result=gross,
        approved_costs=costs,
        net_result=net,
        investor_share_percentage=share,
        distributable_pool=pool,
        total_captured=captured,
        investment_amount=investment,
        participation_percentage=participation,
        investor_return=investor_return,
    )
