from app.repositories import items_repo, stock_repo


def _make_item(conn):
    return items_repo.create_item(conn, name="سجاد فارسي")


def test_insert_and_list_movements(conn, admin_user_id):
    item_id = _make_item(conn)
    stock_repo.insert_stock_movement(
        conn,
        voucher_no="STIN-000001",
        movement_type="in",
        item_id=item_id,
        quantity=10,
        reason=None,
        note=None,
        movement_date="2026-01-01",
        source="manual",
        created_by_user_id=admin_user_id,
    )
    conn.commit()
    rows = stock_repo.list_movements(conn, movement_type="in")
    assert len(rows) == 1
    assert rows[0]["quantity"] == 10


def test_get_by_voucher_no(conn, admin_user_id):
    item_id = _make_item(conn)
    stock_repo.insert_stock_movement(
        conn,
        voucher_no="STOUT-000001",
        movement_type="out",
        item_id=item_id,
        quantity=2,
        reason="تالف",
        note=None,
        movement_date="2026-01-01",
        source="manual",
        created_by_user_id=admin_user_id,
    )
    conn.commit()
    row = stock_repo.get_movement_by_voucher_no(conn, "STOUT-000001")
    assert row is not None
    assert row["reason"] == "تالف"
    assert stock_repo.get_movement_by_voucher_no(conn, "NOPE") is None


def test_get_adjacent_id(conn, admin_user_id):
    item_id = _make_item(conn)
    ids = []
    for i in range(3):
        movement_id = stock_repo.insert_stock_movement(
            conn,
            voucher_no=f"STIN-{i:06d}",
            movement_type="in",
            item_id=item_id,
            quantity=1,
            reason=None,
            note=None,
            movement_date="2026-01-01",
            source="manual",
            created_by_user_id=admin_user_id,
        )
        conn.commit()
        ids.append(movement_id)

    assert stock_repo.get_adjacent_id(conn, ids[1], "previous") == ids[0]
    assert stock_repo.get_adjacent_id(conn, ids[1], "next") == ids[2]
    assert stock_repo.get_adjacent_id(conn, ids[0], "previous") is None
    assert stock_repo.get_adjacent_id(conn, ids[2], "next") is None


def test_update_movement_note(conn, admin_user_id):
    item_id = _make_item(conn)
    movement_id = stock_repo.insert_stock_movement(
        conn,
        voucher_no="STOUT-000002",
        movement_type="out",
        item_id=item_id,
        quantity=1,
        reason="تالف",
        note=None,
        movement_date="2026-01-01",
        source="manual",
        created_by_user_id=admin_user_id,
    )
    conn.commit()
    stock_repo.update_movement_note(conn, movement_id, note="ملاحظة جديدة", reason="إرجاع للمورد")
    conn.commit()
    row = stock_repo.get_movement(conn, movement_id)
    assert row["note"] == "ملاحظة جديدة"
    assert row["reason"] == "إرجاع للمورد"


def test_void_movement(conn, admin_user_id):
    item_id = _make_item(conn)
    movement_id = stock_repo.insert_stock_movement(
        conn,
        voucher_no="STIN-000099",
        movement_type="in",
        item_id=item_id,
        quantity=1,
        reason=None,
        note=None,
        movement_date="2026-01-01",
        source="manual",
        created_by_user_id=admin_user_id,
    )
    conn.commit()
    stock_repo.void_movement(conn, movement_id, admin_user_id)
    conn.commit()
    assert stock_repo.list_movements(conn, movement_type="in") == []
