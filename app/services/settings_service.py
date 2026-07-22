"""Admin-only Settings area: users/permissions, tax rate, override password,
default fees, working days. Gated on is_admin directly (not the one-time
override flow) since the override password itself lives in this screen -
gating Settings behind itself would be circular.
"""

import sqlite3

from app.domain.auth import hash_password
from app.repositories import accounts_repo, settings_repo, users_repo


class NotAuthorized(Exception):
    pass


def _require_admin(user: sqlite3.Row) -> None:
    if not user["is_admin"]:
        raise NotAuthorized("هذا الإجراء متاح للمدير فقط")


def create_user_account(
    conn: sqlite3.Connection,
    admin_user: sqlite3.Row,
    username: str,
    password: str,
    display_name: str,
    permissions: dict | None = None,
    is_admin: bool = False,
) -> int:
    _require_admin(admin_user)
    if not username or not password:
        raise ValueError("اسم المستخدم وكلمة المرور مطلوبان")
    return users_repo.create_user(
        conn, username, hash_password(password), display_name, is_admin, permissions
    )


def update_user_account(
    conn: sqlite3.Connection,
    admin_user: sqlite3.Row,
    target_user_id: int,
    display_name: str | None = None,
    is_admin: bool | None = None,
    permissions: dict | None = None,
) -> None:
    _require_admin(admin_user)
    users_repo.update_user(conn, target_user_id, display_name, is_admin, permissions)


def reset_user_password(
    conn: sqlite3.Connection, admin_user: sqlite3.Row, target_user_id: int, new_password: str
) -> None:
    _require_admin(admin_user)
    users_repo.update_password(conn, target_user_id, hash_password(new_password))


def deactivate_user(conn: sqlite3.Connection, admin_user: sqlite3.Row, target_user_id: int) -> None:
    _require_admin(admin_user)
    users_repo.set_active(conn, target_user_id, False)


def update_shop_settings(conn: sqlite3.Connection, admin_user: sqlite3.Row, **fields) -> None:
    _require_admin(admin_user)
    settings_repo.update_settings(conn, **fields)


def update_override_password(conn: sqlite3.Connection, admin_user: sqlite3.Row, new_password: str) -> None:
    _require_admin(admin_user)
    if not new_password:
        raise ValueError("كلمة مرور التجاوز مطلوبة")
    settings_repo.update_override_password(conn, hash_password(new_password))


def create_account(conn: sqlite3.Connection, admin_user: sqlite3.Row, name: str) -> int:
    _require_admin(admin_user)
    if not name:
        raise ValueError("اسم الحساب مطلوب")
    return accounts_repo.create_account(conn, name)


def deactivate_account(conn: sqlite3.Connection, admin_user: sqlite3.Row, account_id: int) -> None:
    _require_admin(admin_user)
    accounts_repo.set_active(conn, account_id, False)
