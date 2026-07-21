"""Tax computation (الضريبة).

`tax_included` mirrors the invoice checkbox "amount includes tax" (المبلغ
شامل الضريبة): when checked, the entered subtotal is treated as already
tax-inclusive, so nothing is added on top and the tax amount is only backed
out for reporting purposes. When unchecked, tax is added on top.
"""

from dataclasses import dataclass

from app.domain.money import round_half_up_fils


@dataclass(frozen=True)
class TaxResult:
    subtotal_fils: int
    tax_amount_fils: int
    grand_total_fils: int
    tax_rate_percent: float
    tax_included: bool


def compute_tax(subtotal_fils: int, tax_rate_percent: float, tax_included: bool) -> TaxResult:
    if subtotal_fils < 0:
        raise ValueError("subtotal_fils must be non-negative")
    if tax_rate_percent < 0:
        raise ValueError("tax_rate_percent must be non-negative")

    if tax_included:
        if tax_rate_percent == 0:
            tax_amount_fils = 0
        else:
            tax_amount_fils = round_half_up_fils(
                subtotal_fils * tax_rate_percent / (100 + tax_rate_percent)
            )
        grand_total_fils = subtotal_fils
    else:
        tax_amount_fils = round_half_up_fils(subtotal_fils * tax_rate_percent / 100)
        grand_total_fils = subtotal_fils + tax_amount_fils

    return TaxResult(
        subtotal_fils=subtotal_fils,
        tax_amount_fils=tax_amount_fils,
        grand_total_fils=grand_total_fils,
        tax_rate_percent=tax_rate_percent,
        tax_included=tax_included,
    )
