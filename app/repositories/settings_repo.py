"""SQL access for the single-row settings table, including the sequential
invoice/voucher number counters it holds."""

import sqlite3

_COUNTER_COLUMN = {
    # Both invoice types share one plain sequence (no letters) - see
    # SCHEMA_V8_SQL: a cash invoice and an installation invoice created back
    # to back get consecutive numbers (e.g. 1, then 2) regardless of type.
    ("invoice", "cash"): "next_invoice_no",
    ("invoice", "installation"): "next_invoice_no",
    ("voucher", "expense"): "next_expense_voucher_no",
    ("voucher", "purchase"): "next_purchase_voucher_no",
    ("voucher", "receipt"): "next_receipt_voucher_no",
    ("voucher", "stock_in"): "next_stock_in_voucher_no",
    ("voucher", "stock_out"): "next_stock_out_voucher_no",
}

_PREFIX = {
    ("invoice", "cash"): "",
    ("invoice", "installation"): "",
    ("voucher", "expense"): "E",
    ("voucher", "purchase"): "PUR",
    ("voucher", "receipt"): "R",
    ("voucher", "stock_in"): "I",
    ("voucher", "stock_out"): "O",
}


def get_settings(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if row is None:
        raise RuntimeError("settings row missing - database was not seeded")
    return row


def update_settings(conn: sqlite3.Connection, **fields) -> None:
    if not fields:
        return
    allowed = {
        "shop_name_ar",
        "shop_name_en",
        "shop_phone",
        "shop_address",
        "tax_rate_percent",
        "default_installation_fee_fils",
        "default_delivery_fee_fils",
        "late_fine_amount_fils",
        "working_days_per_month",
    }
    set_clauses, values = [], []
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"unknown or protected settings field: {key}")
        set_clauses.append(f"{key} = ?")
        values.append(value)
    set_clauses.append("updated_at = datetime('now')")
    conn.execute(f"UPDATE settings SET {', '.join(set_clauses)} WHERE id = 1", values)
    conn.commit()


def update_override_password(conn: sqlite3.Connection, password_hash: str) -> None:
    conn.execute(
        "UPDATE settings SET override_password_hash = ?, updated_at = datetime('now') WHERE id = 1",
        (password_hash,),
    )
    conn.commit()


def _format_number(prefix: str, value: int) -> str:
    return str(value) if not prefix else f"{prefix}-{value}"


def preview_next_number(conn: sqlite3.Connection, kind: str, subtype: str) -> str:
    """Formats the counter's current value WITHOUT incrementing/reserving it
    - used to show "this is the number a new record will get" before the
    user has actually saved anything (e.g. a voucher/invoice form opening
    with its next number already filled in)."""
    column = _COUNTER_COLUMN[(kind, subtype)]
    prefix = _PREFIX[(kind, subtype)]
    row = conn.execute(f"SELECT {column} FROM settings WHERE id = 1").fetchone()
    return _format_number(prefix, row[0])


def reserve_next_number(conn: sqlite3.Connection, kind: str, subtype: str) -> str:
    """Atomically increments and returns a formatted sequential number, e.g.
    reserve_next_number(conn, "voucher", "expense") -> "E-123" (a single
    letter + a plain unpadded number). Invoices have no prefix at all
    (kind/subtype pairs mapping to an empty _PREFIX entry) -
    reserve_next_number(conn, "invoice", "cash") -> "1", "2", "3", ...
    kind is "invoice" or "voucher"; subtype is "cash"/"installation" or
    "expense"/"purchase"/etc. respectively.
    """
    column = _COUNTER_COLUMN[(kind, subtype)]
    prefix = _PREFIX[(kind, subtype)]
    row = conn.execute(f"SELECT {column} FROM settings WHERE id = 1").fetchone()
    current = row[0]
    conn.execute(f"UPDATE settings SET {column} = ? WHERE id = 1", (current + 1,))
    conn.commit()
    return _format_number(prefix, current)
