"""SQL access for stock_movements - the append-only ledger behind every
inventory change (سند إدخال / سند إخراج, plus automatic 'sale' movements
recorded when an invoice line item matches an inventory item)."""

import sqlite3


def insert_stock_movement(conn: sqlite3.Connection, **fields) -> int:
    """Does not commit - callers wrap this alongside items_repo.adjust_quantity
    in one transaction (see app/services/inventory_service.py)."""
    columns = list(fields.keys())
    placeholders = ",".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO stock_movements ({','.join(columns)}) VALUES ({placeholders})",
        list(fields.values()),
    )
    return cur.lastrowid


def get_movement(conn: sqlite3.Connection, movement_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM stock_movements WHERE id = ?", (movement_id,)).fetchone()


def get_movement_by_voucher_no(conn: sqlite3.Connection, voucher_no: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM stock_movements WHERE voucher_no = ?", (voucher_no,)
    ).fetchone()


def list_movements(
    conn: sqlite3.Connection,
    movement_type: str | None = None,
    source: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    clauses = ["voided_at IS NULL"]
    params: list = []
    if movement_type is not None:
        clauses.append("movement_type = ?")
        params.append(movement_type)
    if source is not None:
        clauses.append("source = ?")
        params.append(source)
    if start_date and end_date:
        clauses.append("date(movement_date) BETWEEN date(?) AND date(?)")
        params.extend([start_date, end_date])
    where = " AND ".join(clauses)
    return conn.execute(
        f"SELECT * FROM stock_movements WHERE {where} ORDER BY movement_date DESC, id DESC",
        params,
    ).fetchall()


def update_movement_note(
    conn: sqlite3.Connection, movement_id: int, note: str | None, reason: str | None = None
) -> None:
    """Edits only the note/reason of a previously-recorded movement - the
    quantity itself is intentionally not editable here (must void + re-enter)
    so quantity_on_hand can never be silently double-adjusted."""
    conn.execute(
        "UPDATE stock_movements SET note = ?, reason = ? WHERE id = ?",
        (note, reason, movement_id),
    )


def void_movement(conn: sqlite3.Connection, movement_id: int, voided_by_user_id: int) -> None:
    """Does not commit - callers must also reverse the quantity_on_hand delta
    via items_repo.adjust_quantity in the same transaction."""
    conn.execute(
        "UPDATE stock_movements SET voided_at = datetime('now'), voided_by_user_id = ? WHERE id = ?",
        (voided_by_user_id, movement_id),
    )


def get_adjacent_id(conn: sqlite3.Connection, current_id: int, direction: str) -> int | None:
    """direction: 'previous' (next-lowest id) or 'next' (next-highest id),
    ordered by creation order - the simplest, least surprising ordering for
    "السند السابق/القادم"."""
    if direction == "previous":
        row = conn.execute(
            "SELECT id FROM stock_movements WHERE id < ? ORDER BY id DESC LIMIT 1", (current_id,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM stock_movements WHERE id > ? ORDER BY id ASC LIMIT 1", (current_id,)
        ).fetchone()
    return row["id"] if row else None


def get_most_recent_movement_id(conn: sqlite3.Connection, movement_type: str) -> int | None:
    """Latest manual (non-voided, non-sale) movement of the given type, by
    creation order - used to jump straight to the latest voucher from a
    blank "new voucher" state."""
    row = conn.execute(
        """SELECT id FROM stock_movements
           WHERE movement_type = ? AND source = 'manual' AND voided_at IS NULL
           ORDER BY id DESC LIMIT 1""",
        (movement_type,),
    ).fetchone()
    return row["id"] if row else None
