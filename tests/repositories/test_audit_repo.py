from app.repositories import audit_repo


def test_log_and_list(conn, admin_user_id):
    audit_repo.log(
        conn,
        user_id=admin_user_id,
        action="permission_override",
        permission="can_create_invoice",
        details="override used to create invoice",
    )
    rows = audit_repo.list_recent(conn)
    assert len(rows) == 1
    assert rows[0]["action"] == "permission_override"
