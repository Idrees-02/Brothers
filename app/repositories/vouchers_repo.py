"""SQL access for expense vouchers (سندات صرف), receipt vouchers (سندات
قبض), and purchase invoices (فواتير شراء). Purchase invoices touch two
tables (header + items) so insert_purchase_invoice/insert_purchase_invoice_item
do not commit - the service layer commits once after both are written."""

import sqlite3


def insert_expense(conn: sqlite3.Connection, **fields) -> int:
    columns = list(fields.keys())
    placeholders = ",".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO expenses ({','.join(columns)}) VALUES ({placeholders})",
        list(fields.values()),
    )
    conn.commit()
    return cur.lastrowid


def list_expenses(
    conn: sqlite3.Connection, start_date: str | None = None, end_date: str | None = None
) -> list[sqlite3.Row]:
    if start_date and end_date:
        return conn.execute(
            """SELECT * FROM expenses WHERE date(expense_date) BETWEEN date(?) AND date(?)
               AND voided_at IS NULL ORDER BY expense_date DESC""",
            (start_date, end_date),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM expenses WHERE voided_at IS NULL ORDER BY expense_date DESC"
    ).fetchall()


def void_expense(conn: sqlite3.Connection, expense_id: int, voided_by_user_id: int) -> None:
    conn.execute(
        "UPDATE expenses SET voided_at = datetime('now'), voided_by_user_id = ? WHERE id = ?",
        (voided_by_user_id, expense_id),
    )
    conn.commit()


def get_expense(conn: sqlite3.Connection, expense_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()


def get_expense_by_voucher_no(conn: sqlite3.Connection, voucher_no: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM expenses WHERE voucher_no = ?", (voucher_no,)).fetchone()


def get_adjacent_expense_id(conn: sqlite3.Connection, current_id: int, direction: str) -> int | None:
    if direction == "previous":
        row = conn.execute(
            "SELECT id FROM expenses WHERE id < ? ORDER BY id DESC LIMIT 1", (current_id,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM expenses WHERE id > ? ORDER BY id ASC LIMIT 1", (current_id,)
        ).fetchone()
    return row["id"] if row else None


def update_expense(conn: sqlite3.Connection, expense_id: int, **fields) -> None:
    """Does not commit - callers wrap this in their own transaction."""
    set_clauses = [f"{key} = ?" for key in fields]
    values = list(fields.values()) + [expense_id]
    conn.execute(f"UPDATE expenses SET {', '.join(set_clauses)} WHERE id = ?", values)


def insert_receipt(conn: sqlite3.Connection, **fields) -> int:
    columns = list(fields.keys())
    placeholders = ",".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO receipts ({','.join(columns)}) VALUES ({placeholders})",
        list(fields.values()),
    )
    conn.commit()
    return cur.lastrowid


def list_receipts(
    conn: sqlite3.Connection, start_date: str | None = None, end_date: str | None = None
) -> list[sqlite3.Row]:
    if start_date and end_date:
        return conn.execute(
            """SELECT * FROM receipts WHERE date(receipt_date) BETWEEN date(?) AND date(?)
               AND voided_at IS NULL ORDER BY receipt_date DESC""",
            (start_date, end_date),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM receipts WHERE voided_at IS NULL ORDER BY receipt_date DESC"
    ).fetchall()


def void_receipt(conn: sqlite3.Connection, receipt_id: int, voided_by_user_id: int) -> None:
    conn.execute(
        "UPDATE receipts SET voided_at = datetime('now'), voided_by_user_id = ? WHERE id = ?",
        (voided_by_user_id, receipt_id),
    )
    conn.commit()


def get_receipt(conn: sqlite3.Connection, receipt_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()


def get_receipt_by_voucher_no(conn: sqlite3.Connection, voucher_no: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM receipts WHERE voucher_no = ?", (voucher_no,)).fetchone()


def get_adjacent_receipt_id(conn: sqlite3.Connection, current_id: int, direction: str) -> int | None:
    if direction == "previous":
        row = conn.execute(
            "SELECT id FROM receipts WHERE id < ? ORDER BY id DESC LIMIT 1", (current_id,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM receipts WHERE id > ? ORDER BY id ASC LIMIT 1", (current_id,)
        ).fetchone()
    return row["id"] if row else None


def update_receipt(conn: sqlite3.Connection, receipt_id: int, **fields) -> None:
    """Does not commit - callers wrap this in their own transaction."""
    set_clauses = [f"{key} = ?" for key in fields]
    values = list(fields.values()) + [receipt_id]
    conn.execute(f"UPDATE receipts SET {', '.join(set_clauses)} WHERE id = ?", values)


def insert_purchase_invoice(conn: sqlite3.Connection, **fields) -> int:
    columns = list(fields.keys())
    placeholders = ",".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO purchase_invoices ({','.join(columns)}) VALUES ({placeholders})",
        list(fields.values()),
    )
    return cur.lastrowid


def insert_purchase_invoice_item(
    conn: sqlite3.Connection,
    purchase_invoice_id: int,
    description: str,
    quantity: float,
    unit_price_fils: int,
    line_total_fils: int,
) -> int:
    cur = conn.execute(
        """INSERT INTO purchase_invoice_items
           (purchase_invoice_id, description, quantity, unit_price_fils, line_total_fils)
           VALUES (?, ?, ?, ?, ?)""",
        (purchase_invoice_id, description, quantity, unit_price_fils, line_total_fils),
    )
    return cur.lastrowid


def get_purchase_invoice(conn: sqlite3.Connection, purchase_invoice_id: int) -> dict | None:
    header = conn.execute(
        "SELECT * FROM purchase_invoices WHERE id = ?", (purchase_invoice_id,)
    ).fetchone()
    if header is None:
        return None
    items = conn.execute(
        "SELECT * FROM purchase_invoice_items WHERE purchase_invoice_id = ? ORDER BY id",
        (purchase_invoice_id,),
    ).fetchall()
    return {"header": header, "items": items}


def list_purchase_invoices(
    conn: sqlite3.Connection, start_date: str | None = None, end_date: str | None = None
) -> list[sqlite3.Row]:
    if start_date and end_date:
        return conn.execute(
            """SELECT * FROM purchase_invoices WHERE date(purchase_date) BETWEEN date(?) AND date(?)
               AND voided_at IS NULL ORDER BY purchase_date DESC""",
            (start_date, end_date),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM purchase_invoices WHERE voided_at IS NULL ORDER BY purchase_date DESC"
    ).fetchall()


def void_purchase_invoice(conn: sqlite3.Connection, purchase_invoice_id: int, voided_by_user_id: int) -> None:
    conn.execute(
        "UPDATE purchase_invoices SET voided_at = datetime('now'), voided_by_user_id = ? WHERE id = ?",
        (voided_by_user_id, purchase_invoice_id),
    )
    conn.commit()
