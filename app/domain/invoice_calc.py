"""Line-item and deposit/remaining-balance math shared by both invoice types."""

from app.domain.money import round_half_up_fils


def line_total_fils(quantity: float, unit_price_fils: int) -> int:
    return round_half_up_fils(quantity * unit_price_fils)


def sum_line_items_fils(items: list[dict]) -> int:
    """items: dicts with 'quantity' and 'unit_price_fils' keys."""
    return sum(line_total_fils(item["quantity"], item["unit_price_fils"]) for item in items)


def remaining_balance_fils(grand_total_fils: int, deposit_fils: int) -> int:
    if deposit_fils < 0:
        raise ValueError("deposit_fils cannot be negative")
    if deposit_fils > grand_total_fils:
        raise ValueError("deposit_fils cannot exceed grand_total_fils")
    return grand_total_fils - deposit_fils
