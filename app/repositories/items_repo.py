"""SQL access for inventory items (المخزون) - name/unit/price plus a
denormalized quantity_on_hand kept in sync by stock_repo's movements."""

import sqlite3


def create_item(
    conn: sqlite3.Connection,
    name: str,
    unit: str = "piece",
    unit_price_fils: int = 0,
) -> int:
    cur = conn.execute(
        "INSERT INTO items (name, unit, unit_price_fils) VALUES (?, ?, ?)",
        (name, unit, unit_price_fils),
    )
    conn.commit()
    return cur.lastrowid


def list_items(conn: sqlite3.Connection, include_inactive: bool = False) -> list[sqlite3.Row]:
    if include_inactive:
        return conn.execute("SELECT * FROM items ORDER BY name").fetchall()
    return conn.execute("SELECT * FROM items WHERE is_active = 1 ORDER BY name").fetchall()


def search_items(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM items WHERE is_active = 1 AND name LIKE ? ORDER BY name",
        (f"%{query}%",),
    ).fetchall()


def get_item(conn: sqlite3.Connection, item_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def find_item_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM items WHERE name = ?", (name,)).fetchone()


def set_active(conn: sqlite3.Connection, item_id: int, is_active: bool) -> None:
    conn.execute("UPDATE items SET is_active = ? WHERE id = ?", (int(is_active), item_id))
    conn.commit()


def adjust_quantity(conn: sqlite3.Connection, item_id: int, delta: float) -> None:
    """Does not commit - callers wrap this alongside a stock_movements insert
    in one transaction (see app/services/inventory_service.py)."""
    conn.execute(
        "UPDATE items SET quantity_on_hand = quantity_on_hand + ?, updated_at = datetime('now','localtime') "
        "WHERE id = ?",
        (delta, item_id),
    )
