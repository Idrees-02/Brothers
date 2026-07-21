"""SQL access for the single-row settings table, including the sequential
invoice/voucher number counters it holds."""

import sqlite3

_COUNTER_COLUMN = {
    ("invoice", "cash"): "next_cash_invoice_no",
    ("invoice", "installation"): "next_installation_invoice_no",
    ("voucher", "expense"): "next_expense_voucher_no",
    ("voucher", "purchase"): "next_purchase_voucher_no",
}

_PREFIX = {
    ("invoice", "cash"): "CASH",
    ("invoice", "installation"): "INST",
    ("voucher", "expense"): "EXP",
    ("voucher", "purchase"): "PUR",
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


def reserve_next_number(conn: sqlite3.Connection, kind: str, subtype: str) -> str:
    """Atomically increments and returns a formatted sequential number, e.g.
    reserve_next_number(conn, "invoice", "cash") -> "CASH-000123".
    kind is "invoice" or "voucher"; subtype is "cash"/"installation" or
    "expense"/"purchase" respectively.
    """
    column = _COUNTER_COLUMN[(kind, subtype)]
    prefix = _PREFIX[(kind, subtype)]
    row = conn.execute(f"SELECT {column} FROM settings WHERE id = 1").fetchone()
    current = row[0]
    conn.execute(f"UPDATE settings SET {column} = ? WHERE id = 1", (current + 1,))
    conn.commit()
    return f"{prefix}-{current:06d}"
