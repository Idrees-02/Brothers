"""Login flow."""

import sqlite3

from app.domain.auth import hash_password, verify_password
from app.repositories import users_repo


class AuthenticationError(Exception):
    pass


def login(conn: sqlite3.Connection, username: str, password: str) -> sqlite3.Row:
    user = users_repo.get_user_by_username(conn, username)
    if user is None or not verify_password(password, user["password_hash"]):
        raise AuthenticationError("اسم المستخدم أو كلمة المرور غير صحيحة")
    return user


def change_password(conn: sqlite3.Connection, user_id: int, new_password: str) -> None:
    users_repo.update_password(conn, user_id, hash_password(new_password))
