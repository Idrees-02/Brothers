import pytest

from app.repositories import items_repo, stock_repo, users_repo
from app.services import inventory_service, invoice_service


def get_admin(conn):
    return users_repo.get_user_by_username(conn, "admin")


def test_create_item(conn):
    admin = get_admin(conn)
    item_id = inventory_service.create_item(
        conn, admin, name="سجاد فارسي", unit="piece", unit_price_fils=5_000,
        override_password_prompt=lambda: None,
    )
    assert items_repo.get_item(conn, item_id)["name"] == "سجاد فارسي"


def test_create_item_rejects_duplicate_name(conn):
    admin = get_admin(conn)
    inventory_service.create_item(
        conn, admin, name="سجاد فارسي", unit="piece", unit_price_fils=5_000,
        override_password_prompt=lambda: None,
    )
    with pytest.raises(ValueError):
        inventory_service.create_item(
            conn, admin, name="سجاد فارسي", unit="piece", unit_price_fils=6_000,
            override_password_prompt=lambda: None,
        )


def test_record_stock_in_increases_quantity(conn):
    admin = get_admin(conn)
    item_id = inventory_service.create_item(
        conn, admin, name="سجاد", unit="piece", unit_price_fils=1_000,
        override_password_prompt=lambda: None,
    )
    inventory_service.record_stock_in(
        conn, admin, item_id=item_id, quantity=10, movement_date="2026-01-01",
        override_password_prompt=lambda: None,
    )
    assert items_repo.get_item(conn, item_id)["quantity_on_hand"] == 10


def test_record_stock_out_decreases_quantity(conn):
    admin = get_admin(conn)
    item_id = inventory_service.create_item(
        conn, admin, name="سجاد", unit="piece", unit_price_fils=1_000,
        override_password_prompt=lambda: None,
    )
    inventory_service.record_stock_in(
        conn, admin, item_id=item_id, quantity=10, movement_date="2026-01-01",
        override_password_prompt=lambda: None,
    )
    inventory_service.record_stock_out(
        conn, admin, item_id=item_id, quantity=4, reason="تالف", movement_date="2026-01-02",
        override_password_prompt=lambda: None,
    )
    assert items_repo.get_item(conn, item_id)["quantity_on_hand"] == 6


def test_record_stock_out_rejects_insufficient_quantity(conn):
    admin = get_admin(conn)
    item_id = inventory_service.create_item(
        conn, admin, name="سجاد", unit="piece", unit_price_fils=1_000,
        override_password_prompt=lambda: None,
    )
    with pytest.raises(ValueError):
        inventory_service.record_stock_out(
            conn, admin, item_id=item_id, quantity=1, reason="تالف", movement_date="2026-01-01",
            override_password_prompt=lambda: None,
        )
    # rejection must not have partially applied - quantity stays untouched
    assert items_repo.get_item(conn, item_id)["quantity_on_hand"] == 0


def test_record_stock_out_requires_reason(conn):
    admin = get_admin(conn)
    item_id = inventory_service.create_item(
        conn, admin, name="سجاد", unit="piece", unit_price_fils=1_000,
        override_password_prompt=lambda: None,
    )
    inventory_service.record_stock_in(
        conn, admin, item_id=item_id, quantity=5, movement_date="2026-01-01",
        override_password_prompt=lambda: None,
    )
    with pytest.raises(ValueError):
        inventory_service.record_stock_out(
            conn, admin, item_id=item_id, quantity=1, reason="", movement_date="2026-01-01",
            override_password_prompt=lambda: None,
        )


def test_voucher_numbers_are_sequential_per_kind(conn):
    admin = get_admin(conn)
    item_id = inventory_service.create_item(
        conn, admin, name="سجاد", unit="piece", unit_price_fils=1_000,
        override_password_prompt=lambda: None,
    )
    id1 = inventory_service.record_stock_in(
        conn, admin, item_id=item_id, quantity=1, movement_date="2026-01-01",
        override_password_prompt=lambda: None,
    )
    id2 = inventory_service.record_stock_in(
        conn, admin, item_id=item_id, quantity=1, movement_date="2026-01-01",
        override_password_prompt=lambda: None,
    )
    assert stock_repo.get_movement(conn, id1)["voucher_no"] == "STIN-000001"
    assert stock_repo.get_movement(conn, id2)["voucher_no"] == "STIN-000002"


def test_selling_an_inventory_linked_item_decrements_stock(conn):
    admin = get_admin(conn)
    item_id = inventory_service.create_item(
        conn, admin, name="سجاد فارسي", unit="piece", unit_price_fils=5_000,
        override_password_prompt=lambda: None,
    )
    inventory_service.record_stock_in(
        conn, admin, item_id=item_id, quantity=10, movement_date="2026-01-01",
        override_password_prompt=lambda: None,
    )

    invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="39112233",
        items=[{"description": "سجاد فارسي", "quantity": 3, "unit_price_fils": 5_000}],
        tax_included=False,
        payment_method="cash",
        override_password_prompt=lambda: None,
    )

    assert items_repo.get_item(conn, item_id)["quantity_on_hand"] == 7
    sale_movements = stock_repo.list_movements(conn, movement_type="out", source="sale")
    assert len(sale_movements) == 1
    assert sale_movements[0]["quantity"] == 3


def test_selling_an_item_with_no_inventory_match_does_not_error(conn):
    admin = get_admin(conn)
    # No matching inventory item exists for this description - the sale must
    # still succeed and simply not touch the inventory ledger.
    invoice_id = invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="39112233",
        items=[{"description": "منتج غير مخزّن", "quantity": 1, "unit_price_fils": 1_000}],
        tax_included=False,
        payment_method="cash",
        override_password_prompt=lambda: None,
    )
    assert invoice_id is not None
    assert stock_repo.list_movements(conn, movement_type="out", source="sale") == []
