"""Money helpers. All money is stored/computed as an integer number of fils
(1 BHD = 1000 fils, matching Bahraini Dinar's 3-decimal-place fils unit).
Conversion to/from human-readable BHD strings happens only at the UI/print
boundary - never do fils arithmetic with floats elsewhere.
"""

from decimal import ROUND_HALF_UP, Decimal

FILS_PER_BHD = 1000


def bhd_to_fils(amount: str | float | Decimal) -> int:
    """Parse a BHD amount (e.g. "12.5", 12.500, Decimal("12.500")) to fils."""
    d = Decimal(str(amount))
    return int((d * FILS_PER_BHD).to_integral_value(rounding=ROUND_HALF_UP))


def fils_to_bhd_str(fils: int) -> str:
    """Format fils as a 3-decimal BHD string, e.g. 12500 -> "12.500"."""
    sign = "-" if fils < 0 else ""
    whole, rem = divmod(abs(fils), FILS_PER_BHD)
    return f"{sign}{whole}.{rem:03d}"


def round_half_up_fils(value: float | Decimal) -> int:
    """Round a fractional fils value to the nearest integer fils, half-up."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
