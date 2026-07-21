"""End-of-month salary computation.

final_pay = base_salary - withdrawals - absence_deduction - late_deduction
  daily_rate           = base_salary / working_days_per_month (Settings-configurable)
  absence_deduction    = daily_rate * absent_days
  late_deduction       = late_fine_amount_fils * late_occurrences (fixed fine per occurrence)
"""

from dataclasses import dataclass

from app.domain.money import round_half_up_fils


@dataclass(frozen=True)
class SalaryBreakdown:
    base_salary_fils: int
    withdrawals_fils: int
    absent_days: int
    daily_rate_fils: int
    absence_deduction_fils: int
    late_occurrences: int
    late_fine_amount_fils: int
    late_deduction_fils: int
    final_pay_fils: int


def compute_salary(
    base_salary_fils: int,
    withdrawals_fils: int,
    absent_days: int,
    working_days_per_month: int,
    late_occurrences: int,
    late_fine_amount_fils: int,
) -> SalaryBreakdown:
    if working_days_per_month <= 0:
        raise ValueError("working_days_per_month must be positive")

    daily_rate_fils = round_half_up_fils(base_salary_fils / working_days_per_month)
    absence_deduction_fils = daily_rate_fils * absent_days
    late_deduction_fils = late_fine_amount_fils * late_occurrences
    final_pay_fils = (
        base_salary_fils - withdrawals_fils - absence_deduction_fils - late_deduction_fils
    )

    return SalaryBreakdown(
        base_salary_fils=base_salary_fils,
        withdrawals_fils=withdrawals_fils,
        absent_days=absent_days,
        daily_rate_fils=daily_rate_fils,
        absence_deduction_fils=absence_deduction_fils,
        late_occurrences=late_occurrences,
        late_fine_amount_fils=late_fine_amount_fils,
        late_deduction_fils=late_deduction_fils,
        final_pay_fils=final_pay_fils,
    )
