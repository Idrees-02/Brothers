"""Audit log writes - one row per permission override use or voided record,
for financial accountability."""

import sqlite3


def log(
    conn: sqlite3.Connection,
    user_id: int | None,
    action: str,
    permission: str | None = None,
    target_table: str | None = None,
    target_id: int | None = None,
    details: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO audit_log (user_id, action, permission, target_table, target_id, details)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, action, permission, target_table, target_id, details),
    )
    conn.commit()
    return cur.lastrowid


def list_recent(conn: sqlite3.Connection, limit: int = 200) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM audit_log ORDER BY occurred_at DESC LIMIT ?", (limit,)
    ).fetchall()
