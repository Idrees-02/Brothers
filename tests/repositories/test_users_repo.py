from app.repositories import users_repo


def test_create_and_fetch_user(conn):
    user_id = users_repo.create_user(
        conn,
        username="sara",
        password_hash="hash",
        display_name="سارة",
        permissions={"can_create_invoice": True},
    )
    row = users_repo.get_user_by_id(conn, user_id)
    assert row["username"] == "sara"
    assert row["can_create_invoice"] == 1
    assert row["can_edit_invoice"] == 0


def test_deactivated_user_not_returned_by_username(conn):
    user_id = users_repo.create_user(conn, "temp", "hash", "مؤقت")
    users_repo.set_active(conn, user_id, False)
    assert users_repo.get_user_by_username(conn, "temp") is None
    assert users_repo.get_user_by_id(conn, user_id)["is_active"] == 0


def test_update_user_permissions(conn):
    user_id = users_repo.create_user(conn, "sara", "hash", "سارة")
    users_repo.update_user(conn, user_id, permissions={"can_create_voucher": True})
    row = users_repo.get_user_by_id(conn, user_id)
    assert row["can_create_voucher"] == 1
