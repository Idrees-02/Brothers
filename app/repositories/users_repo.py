"""SQL access for the users table. No business rules here - see
app/domain/permissions.py and app/services/auth_service.py for those."""

import sqlite3

PERMISSION_COLUMNS = (
    "can_create_invoice",
    "can_edit_invoice",
    "can_view_only",
    "can_create_voucher",
    "can_register_attendance",
)


def create_user(
    conn: sqlite3.Connection,
    username: str,
    password_hash: str,
    display_name: str,
    is_admin: bool = False,
    permissions: dict | None = None,
) -> int:
    permissions = permissions or {}
    columns = ["username", "password_hash", "display_name", "is_admin"] + list(PERMISSION_COLUMNS)
    values = [username, password_hash, display_name, int(is_admin)] + [
        int(permissions.get(col, False)) for col in PERMISSION_COLUMNS
    ]
    placeholders = ",".join("?" for _ in columns)
    cur = conn.execute(
        f"INSERT INTO users ({','.join(columns)}) VALUES ({placeholders})", values
    )
    conn.commit()
    return cur.lastrowid


def get_user_by_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE username = ? AND is_active = 1", (username,)
    ).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_users(conn: sqlite3.Connection, include_inactive: bool = False) -> list[sqlite3.Row]:
    if include_inactive:
        return conn.execute("SELECT * FROM users ORDER BY username").fetchall()
    return conn.execute(
        "SELECT * FROM users WHERE is_active = 1 ORDER BY username"
    ).fetchall()


def update_user(
    conn: sqlite3.Connection,
    user_id: int,
    display_name: str | None = None,
    is_admin: bool | None = None,
    permissions: dict | None = None,
) -> None:
    fields, values = [], []
    if display_name is not None:
        fields.append("display_name = ?")
        values.append(display_name)
    if is_admin is not None:
        fields.append("is_admin = ?")
        values.append(int(is_admin))
    if permissions:
        for col in PERMISSION_COLUMNS:
            if col in permissions:
                fields.append(f"{col} = ?")
                values.append(int(permissions[col]))
    if not fields:
        return
    fields.append("updated_at = datetime('now')")
    values.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()


def update_password(conn: sqlite3.Connection, user_id: int, password_hash: str) -> None:
    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
        (password_hash, user_id),
    )
    conn.commit()


def set_active(conn: sqlite3.Connection, user_id: int, is_active: bool) -> None:
    conn.execute(
        "UPDATE users SET is_active = ?, updated_at = datetime('now') WHERE id = ?",
        (int(is_active), user_id),
    )
    conn.commit()
