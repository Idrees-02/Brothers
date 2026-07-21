import pytest

from app.domain.invoice_calc import (
    line_total_fils,
    remaining_balance_fils,
    sum_line_items_fils,
)


def test_line_total_sqm_pricing():
    # 2.5 sqm at 5.000 BHD/sqm (5000 fils) = 12.500 BHD
    assert line_total_fils(2.5, 5_000) == 12_500


def test_sum_line_items():
    items = [
        {"quantity": 2.5, "unit_price_fils": 5_000},
        {"quantity": 1, "unit_price_fils": 3_000},
    ]
    assert sum_line_items_fils(items) == 12_500 + 3_000


def test_remaining_balance():
    assert remaining_balance_fils(20_000, 5_000) == 15_000


def test_remaining_balance_full_deposit():
    assert remaining_balance_fils(20_000, 20_000) == 0


def test_deposit_exceeds_total_rejected():
    with pytest.raises(ValueError):
        remaining_balance_fils(20_000, 25_000)


def test_negative_deposit_rejected():
    with pytest.raises(ValueError):
        remaining_balance_fils(20_000, -1)
