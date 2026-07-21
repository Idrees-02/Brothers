"""SQL access for expense vouchers (سندات صرف) and purchase invoices
(فواتير شراء). Purchase invoices touch two tables (header + items) so
insert_purchase_invoice/insert_purchase_invoice_item do not commit - the
service layer commits once after both are written."""

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
