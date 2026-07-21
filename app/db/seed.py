"""First-run seeding: default admin user + default settings row.

The seeded admin password and override password are intentionally simple
defaults documented in the README - the admin must change them from the
Settings screen immediately after first login.
"""

import sqlite3

from app.domain.auth import hash_password

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def seed_if_empty(conn: sqlite3.Connection, default_override_password: str = "0000") -> None:
    has_settings = conn.execute("SELECT 1 FROM settings WHERE id = 1").fetchone()
    if not has_settings:
        conn.execute(
            "INSERT INTO settings (id, override_password_hash) VALUES (1, ?)",
            (hash_password(default_override_password),),
        )

    has_admin = conn.execute(
        "SELECT 1 FROM users WHERE username = ?", (DEFAULT_ADMIN_USERNAME,)
    ).fetchone()
    if not has_admin:
        conn.execute(
            """
            INSERT INTO users (
                username, password_hash, display_name, is_admin,
                can_create_invoice, can_edit_invoice, can_view_only,
                can_create_voucher, can_register_attendance
            ) VALUES (?, ?, ?, 1, 1, 1, 0, 1, 1)
            """,
            (
                DEFAULT_ADMIN_USERNAME,
                hash_password(DEFAULT_ADMIN_PASSWORD),
                "المدير",
            ),
        )
    conn.commit()
