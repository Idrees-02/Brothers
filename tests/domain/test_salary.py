import pytest

from app.domain.salary import compute_salary


def test_full_deductions():
    result = compute_salary(
        base_salary_fils=300_000,
        withdrawals_fils=50_000,
        absent_days=2,
        working_days_per_month=26,
        late_occurrences=3,
        late_fine_amount_fils=2_000,
    )
    assert result.daily_rate_fils == 11_538  # round(300000/26) = round(11538.46)
    assert result.absence_deduction_fils == 23_076
    assert result.late_deduction_fils == 6_000
    assert result.final_pay_fils == 300_000 - 50_000 - 23_076 - 6_000


def test_no_deductions():
    result = compute_salary(
        base_salary_fils=300_000,
        withdrawals_fils=0,
        absent_days=0,
        working_days_per_month=26,
        late_occurrences=0,
        late_fine_amount_fils=2_000,
    )
    assert result.final_pay_fils == 300_000


def test_invalid_working_days_rejected():
    with pytest.raises(ValueError):
        compute_salary(300_000, 0, 0, 0, 0, 0)
