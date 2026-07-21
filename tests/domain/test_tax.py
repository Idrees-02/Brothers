from app.domain.tax import compute_tax


def test_tax_excluded_adds_on_top():
    result = compute_tax(subtotal_fils=10_000, tax_rate_percent=10.0, tax_included=False)
    assert result.tax_amount_fils == 1_000
    assert result.grand_total_fils == 11_000


def test_tax_included_does_not_add_on_top():
    # 10 BHD carpet, price treated as already including 10% tax -> total stays 10 BHD
    result = compute_tax(subtotal_fils=10_000, tax_rate_percent=10.0, tax_included=True)
    assert result.grand_total_fils == 10_000
    # tax amount is backed out for reporting only: 10000 * 10 / 110 = 909.09 -> 909
    assert result.tax_amount_fils == 909


def test_zero_rate():
    excluded = compute_tax(10_000, 0.0, tax_included=False)
    included = compute_tax(10_000, 0.0, tax_included=True)
    assert excluded.tax_amount_fils == 0
    assert excluded.grand_total_fils == 10_000
    assert included.tax_amount_fils == 0
    assert included.grand_total_fils == 10_000


def test_negative_subtotal_rejected():
    import pytest

    with pytest.raises(ValueError):
        compute_tax(-1, 10.0, False)
