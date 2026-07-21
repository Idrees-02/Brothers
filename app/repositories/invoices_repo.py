"""SQL access for invoices + invoice_items + invoice_payments.

Unlike users_repo/settings_repo (single-statement operations that commit
immediately), creating an invoice touches three tables. The insert_* /
void_invoice functions here do NOT commit - app/services/invoice_service.py
wraps a full creation flow in one transaction and commits/rolls back once,
so a crash mid-creation can never leave a header row with no line items.
"""

import sqlite3


def insert_invoice(conn: sqlite3.Connection, **fields) -> int:
    columns = list(fields.keys())
    placeholders = ",".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO invoices ({','.join(columns)}) VALUES ({placeholders})",
        list(fields.values()),
    )
    return cur.lastrowid


def insert_invoice_item(
    conn: sqlite3.Connection,
    invoice_id: int,
    description: str,
    quantity: float,
    unit: str,
    unit_price_fils: int,
    line_total_fils: int,
) -> int:
    cur = conn.execute(
        """INSERT INTO invoice_items
           (invoice_id, description, quantity, unit, unit_price_fils, line_total_fils)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (invoice_id, description, quantity, unit, unit_price_fils, line_total_fils),
    )
    return cur.lastrowid


def insert_invoice_payment(
    conn: sqlite3.Connection,
    invoice_id: int,
    payment_type: str,
    amount_fils: int,
    received_by_user_id: int,
) -> int:
    cur = conn.execute(
        """INSERT INTO invoice_payments (invoice_id, payment_type, amount_fils, received_by_user_id)
           VALUES (?, ?, ?, ?)""",
        (invoice_id, payment_type, amount_fils, received_by_user_id),
    )
    return cur.lastrowid


def set_invoice_status(conn: sqlite3.Connection, invoice_id: int, status: str) -> None:
    conn.execute(
        "UPDATE invoices SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, invoice_id),
    )


def void_invoice(conn: sqlite3.Connection, invoice_id: int, voided_by_user_id: int) -> None:
    conn.execute(
        """UPDATE invoices
           SET status = 'voided', voided_at = datetime('now'), voided_by_user_id = ?
           WHERE id = ?""",
        (voided_by_user_id, invoice_id),
    )


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> dict | None:
    header = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if header is None:
        return None
    items = conn.execute(
        "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id", (invoice_id,)
    ).fetchall()
    payments = conn.execute(
        "SELECT * FROM invoice_payments WHERE invoice_id = ? ORDER BY id", (invoice_id,)
    ).fetchall()
    return {"header": header, "items": items, "payments": payments}


def search_invoices(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    like = f"%{query}%"
    return conn.execute(
        """SELECT * FROM invoices
           WHERE invoice_no LIKE ? OR customer_name LIKE ? OR phone LIKE ? OR address LIKE ?
           ORDER BY created_at DESC""",
        (like, like, like, like),
    ).fetchall()


def list_invoices_between(
    conn: sqlite3.Connection, start_date: str, end_date: str, exclude_voided: bool = True
) -> list[sqlite3.Row]:
    status_clause = "AND status != 'voided'" if exclude_voided else ""
    return conn.execute(
        f"""SELECT * FROM invoices
            WHERE date(created_at) BETWEEN date(?) AND date(?) {status_clause}
            ORDER BY created_at""",
        (start_date, end_date),
    ).fetchall()
