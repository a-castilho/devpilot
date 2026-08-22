from decimal import Decimal

import pytest

from app.services.investia_finance import calculate_distribution, calculate_participation


def test_distribution_uses_net_result_after_approved_costs():
    preview = calculate_distribution(
        gross_result="100000",
        approved_costs="35000",
        investor_share_percentage="30",
        total_captured="80000",
        investment_amount="1000",
    )

    assert preview.net_result == Decimal("65000.00")
    assert preview.distributable_pool == Decimal("19500.00")
    assert preview.participation_percentage == Decimal("1.2500")
    assert preview.investor_return == Decimal("243.75")


def test_distribution_never_turns_negative_result_into_negative_pool():
    preview = calculate_distribution(
        gross_result="10000",
        approved_costs="15000",
        investor_share_percentage="30",
        total_captured="80000",
        investment_amount="1000",
    )

    assert preview.net_result == Decimal("0.00")
    assert preview.distributable_pool == Decimal("0.00")
    assert preview.investor_return == Decimal("0.00")


def test_participation_rejects_investment_above_total_captured():
    with pytest.raises(ValueError, match="cannot exceed"):
        calculate_participation("90000", "80000")


def test_investor_share_is_bounded_to_one_hundred_percent():
    with pytest.raises(ValueError, match="between 0 and 100"):
        calculate_distribution(
            gross_result="1000",
            approved_costs="0",
            investor_share_percentage="101",
            total_captured="1000",
        )
