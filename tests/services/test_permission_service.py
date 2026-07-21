import pytest

from app.domain.permissions import Permission
from app.repositories import settings_repo, users_repo
from app.services.permission_service import PermissionDenied, require_permission


def make_unprivileged_user(conn):
    user_id = users_repo.create_user(conn, "clerk", "hash", "موظف")
    return users_repo.get_user_by_id(conn, user_id)


def test_permitted_user_passes_without_prompt(conn):
    user_id = users_repo.create_user(
        conn, "clerk", "hash", "موظف", permissions={"can_create_invoice": True}
    )
    user = users_repo.get_user_by_id(conn, user_id)
    called = False

    def prompt():
        nonlocal called
        called = True
        return None

    require_permission(conn, user, Permission.CREATE_INVOICE, "test", prompt)
    assert called is False


def test_correct_override_password_allows_once_and_logs(conn):
    user = make_unprivileged_user(conn)
    require_permission(conn, user, Permission.CREATE_INVOICE, "test action", lambda: "0000")

    rows = conn.execute("SELECT * FROM audit_log").fetchall()
    assert len(rows) == 1
    assert rows[0]["action"] == "permission_override"
    assert rows[0]["permission"] == Permission.CREATE_INVOICE.value

    # confirm nothing persisted as a standing grant
    refreshed = users_repo.get_user_by_id(conn, user["id"])
    assert refreshed["can_create_invoice"] == 0


def test_wrong_override_password_denies(conn):
    user = make_unprivileged_user(conn)
    with pytest.raises(PermissionDenied):
        require_permission(conn, user, Permission.CREATE_INVOICE, "test", lambda: "wrong")


def test_cancelled_prompt_denies(conn):
    user = make_unprivileged_user(conn)
    with pytest.raises(PermissionDenied):
        require_permission(conn, user, Permission.CREATE_INVOICE, "test", lambda: None)
