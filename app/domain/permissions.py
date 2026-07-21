"""Permission predicate. The one-time override flow itself lives in
app/services/permission_service.py since it needs DB/settings access -
this module only decides whether a user's stored flags already allow
an action.
"""

from enum import Enum


class Permission(str, Enum):
    CREATE_INVOICE = "can_create_invoice"
    EDIT_INVOICE = "can_edit_invoice"
    VIEW_ONLY = "can_view_only"
    CREATE_VOUCHER = "can_create_voucher"
    REGISTER_ATTENDANCE = "can_register_attendance"


# Permissions that can_view_only vetoes even if their own flag is also set -
# an admin misconfiguration (e.g. both can_view_only and can_create_invoice
# set) should not silently grant write access.
_BLOCKED_BY_VIEW_ONLY = {
    Permission.CREATE_INVOICE,
    Permission.EDIT_INVOICE,
    Permission.CREATE_VOUCHER,
}


def user_has_permission(user_row, permission: Permission) -> bool:
    if user_row["is_admin"]:
        return True
    if permission in _BLOCKED_BY_VIEW_ONLY and user_row["can_view_only"]:
        return False
    return bool(user_row[permission.value])
