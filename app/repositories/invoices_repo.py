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


def delete_invoice_items(conn: sqlite3.Connection, invoice_id: int) -> None:
    conn.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))


def update_invoice_header(conn: sqlite3.Connection, invoice_id: int, **fields) -> None:
    set_clauses = [f"{key} = ?" for key in fields]
    set_clauses.append("updated_at = datetime('now')")
    values = list(fields.values()) + [invoice_id]
    conn.execute(f"UPDATE invoices SET {', '.join(set_clauses)} WHERE id = ?", values)


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


def list_unpaid_invoices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Invoices still carrying a remaining balance - status stays 'booked'
    until record_remaining_payment collects the last fils."""
    return conn.execute(
        "SELECT * FROM invoices WHERE status = 'booked' ORDER BY created_at DESC"
    ).fetchall()


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


def list_all_invoices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM invoices ORDER BY created_at DESC").fetchall()


def get_by_invoice_no(conn: sqlite3.Connection, invoice_no: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM invoices WHERE invoice_no = ?", (invoice_no,)).fetchone()


def get_adjacent_id(conn: sqlite3.Connection, current_id: int, direction: str) -> int | None:
    """direction: 'previous' (next-lowest id) or 'next' (next-highest id),
    ordered by creation order - the simplest, least surprising ordering for
    "الفاتورة السابقة/القادمة"."""
    if direction == "previous":
        row = conn.execute(
            "SELECT id FROM invoices WHERE id < ? ORDER BY id DESC LIMIT 1", (current_id,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM invoices WHERE id > ? ORDER BY id ASC LIMIT 1", (current_id,)
        ).fetchone()
    return row["id"] if row else None


def count_invoices_created_on(conn: sqlite3.Connection, work_date: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM invoices WHERE date(created_at) = date(?) AND status != 'voided'",
        (work_date,),
    ).fetchone()
    return row["cnt"]


def list_installations_for_date(conn: sqlite3.Connection, work_date: str) -> list[sqlite3.Row]:
    """Installation-type invoices AND delivery-flagged cash invoices
    scheduled for work_date, joined with the assigned employee's name - both
    go through the exact same scheduling screen/outcome workflow."""
    return conn.execute(
        """SELECT invoices.*, employees.full_name AS assigned_employee_name
           FROM invoices
           LEFT JOIN employees ON employees.id = invoices.assigned_employee_id
           WHERE (invoices.invoice_type = 'installation' OR invoices.with_delivery = 1)
             AND invoices.installation_date = date(?)
             AND invoices.status != 'voided'
           ORDER BY invoices.created_at""",
        (work_date,),
    ).fetchall()


def list_unscheduled_installations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Pending installation/delivery invoices with NO installation date -
    typically ones postponed indefinitely - so they can be found again and
    rescheduled instead of silently dropping out of every day's schedule."""
    return conn.execute(
        """SELECT invoices.*, employees.full_name AS assigned_employee_name
           FROM invoices
           LEFT JOIN employees ON employees.id = invoices.assigned_employee_id
           WHERE (invoices.invoice_type = 'installation' OR invoices.with_delivery = 1)
             AND invoices.installation_date IS NULL
             AND invoices.installation_status IN ('pending','postponed')
             AND invoices.status != 'voided'
           ORDER BY invoices.created_at""",
    ).fetchall()


def count_installations_for_date(conn: sqlite3.Connection, work_date: str) -> int:
    row = conn.execute(
        """SELECT COUNT(*) AS cnt FROM invoices
           WHERE (invoice_type = 'installation' OR with_delivery = 1) AND installation_date = date(?)
             AND status != 'voided'""",
        (work_date,),
    ).fetchone()
    return row["cnt"]


def assign_installer(conn: sqlite3.Connection, invoice_id: int, employee_id: int | None) -> None:
    conn.execute(
        "UPDATE invoices SET assigned_employee_id = ?, updated_at = datetime('now') WHERE id = ?",
        (employee_id, invoice_id),
    )
    conn.commit()


def set_installation_status(
    conn: sqlite3.Connection,
    invoice_id: int,
    installation_status: str,
    installation_date: str | None = None,
) -> None:
    """Updates installation_status; also updates installation_date when a
    new one is supplied (used for postpone-with-new-date and reschedule)."""
    if installation_date is not None:
        conn.execute(
            """UPDATE invoices SET installation_status = ?, installation_date = ?,
               updated_at = datetime('now') WHERE id = ?""",
            (installation_status, installation_date, invoice_id),
        )
    else:
        conn.execute(
            "UPDATE invoices SET installation_status = ?, updated_at = datetime('now') WHERE id = ?",
            (installation_status, invoice_id),
        )
    conn.commit()


def clear_installation_date(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Used for 'postpone without a new date' - keeps the invoice out of any
    specific day's schedule until someone assigns it a new date."""
    conn.execute(
        """UPDATE invoices SET installation_date = NULL, installation_status = 'postponed',
           updated_at = datetime('now') WHERE id = ?""",
        (invoice_id,),
    )
    conn.commit()
