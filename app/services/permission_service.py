"""One-time permission override gating.

If the acting user already has the permission, this is a no-op. Otherwise
the UI-supplied callback is used to prompt for the override password; a
correct entry lets that single action through and is logged to audit_log -
it never grants a standing permission.
"""

import sqlite3
from typing import Callable

from app.domain.auth import verify_password
from app.domain.permissions import Permission, user_has_permission
from app.repositories import audit_repo, settings_repo

OverridePrompt = Callable[[], str | None]


class PermissionDenied(Exception):
    def __init__(self, permission: Permission):
        self.permission = permission
        super().__init__(f"permission denied: {permission.value}")


def require_permission(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    permission: Permission,
    action_label: str,
    override_password_prompt: OverridePrompt,
) -> None:
    if user_has_permission(user, permission):
        return

    entered = override_password_prompt()
    if entered is None:
        raise PermissionDenied(permission)

    settings = settings_repo.get_settings(conn)
    if not verify_password(entered, settings["override_password_hash"]):
        raise PermissionDenied(permission)

    audit_repo.log(
        conn,
        user_id=user["id"],
        action="permission_override",
        permission=permission.value,
        details=action_label,
    )
