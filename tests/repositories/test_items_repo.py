from app.repositories import items_repo


def test_create_and_list_items(conn):
    item_id = items_repo.create_item(conn, name="سجاد فارسي", unit="piece", unit_price_fils=5_000)
    rows = items_repo.list_items(conn)
    assert len(rows) == 1
    assert rows[0]["id"] == item_id
    assert rows[0]["quantity_on_hand"] == 0


def test_find_item_by_name(conn):
    items_repo.create_item(conn, name="سجاد تركي")
    assert items_repo.find_item_by_name(conn, "سجاد تركي") is not None
    assert items_repo.find_item_by_name(conn, "غير موجود") is None


def test_adjust_quantity(conn):
    item_id = items_repo.create_item(conn, name="سجاد")
    items_repo.adjust_quantity(conn, item_id, 10)
    conn.commit()
    assert items_repo.get_item(conn, item_id)["quantity_on_hand"] == 10

    items_repo.adjust_quantity(conn, item_id, -3)
    conn.commit()
    assert items_repo.get_item(conn, item_id)["quantity_on_hand"] == 7


def test_set_active_hides_from_default_listing(conn):
    item_id = items_repo.create_item(conn, name="سجاد قديم")
    items_repo.set_active(conn, item_id, False)
    assert items_repo.list_items(conn) == []
    assert len(items_repo.list_items(conn, include_inactive=True)) == 1


def test_search_items(conn):
    items_repo.create_item(conn, name="سجاد فارسي")
    items_repo.create_item(conn, name="سجاد تركي")
    items_repo.create_item(conn, name="ستارة")
    results = items_repo.search_items(conn, "سجاد")
    assert {row["name"] for row in results} == {"سجاد فارسي", "سجاد تركي"}
