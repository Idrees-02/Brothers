import pytest

from app.repositories import invoices_repo, users_repo
from app.services import invoice_service


def get_admin(conn):
    return users_repo.get_user_by_username(conn, "admin")


def test_create_cash_invoice_defaults_customer_name(conn):
    admin = get_admin(conn)
    invoice_id = invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="33330000",
        items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
        tax_included=False,
        override_password_prompt=lambda: None,
    )
    fetched = invoices_repo.get_invoice(conn, invoice_id)
    assert fetched["header"]["customer_name"] == "نقدي"
    assert fetched["header"]["grand_total_fils"] == 11_000  # 10% tax added on top
    assert fetched["header"]["status"] == "completed"
    assert len(fetched["payments"]) == 1
    assert fetched["payments"][0]["payment_type"] == "full"


def test_create_cash_invoice_requires_phone(conn):
    admin = get_admin(conn)
    with pytest.raises(ValueError):
        invoice_service.create_cash_invoice(
            conn,
            admin,
            phone="",
            items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
            tax_included=False,
            override_password_prompt=lambda: None,
        )


def test_create_installation_invoice_with_deposit_stays_booked(conn):
    admin = get_admin(conn)
    invoice_id = invoice_service.create_installation_invoice(
        conn,
        admin,
        customer_name="أحمد",
        phone="33334444",
        area_region="المحرق",
        items=[{"description": "سجاد مقاس خاص", "quantity": 5, "unit_price_fils": 4_000}],
        with_installation=False,
        deposit_fils=5_000,
        tax_included=False,
        override_password_prompt=lambda: None,
    )
    fetched = invoices_repo.get_invoice(conn, invoice_id)
    header = fetched["header"]
    assert header["status"] == "booked"
    assert header["subtotal_fils"] == 20_000
    assert header["tax_amount_fils"] == 2_000
    assert header["grand_total_fils"] == 22_000
    assert header["deposit_fils"] == 5_000


def test_create_installation_invoice_requires_area_region(conn):
    admin = get_admin(conn)
    with pytest.raises(ValueError):
        invoice_service.create_installation_invoice(
            conn,
            admin,
            customer_name="أحمد",
            phone="33334444",
            area_region="",
            items=[{"description": "سجاد", "quantity": 1, "unit_price_fils": 4_000}],
            with_installation=False,
            deposit_fils=0,
            tax_included=False,
            override_password_prompt=lambda: None,
        )


def test_installation_fee_added_when_with_installation(conn):
    from app.repositories import settings_repo

    settings_repo.update_settings(conn, default_installation_fee_fils=3_000)
    admin = get_admin(conn)
    invoice_id = invoice_service.create_installation_invoice(
        conn,
        admin,
        customer_name="أحمد",
        phone="33334444",
        area_region="المحرق",
        items=[{"description": "سجاد", "quantity": 1, "unit_price_fils": 10_000}],
        with_installation=True,
        deposit_fils=0,
        tax_included=False,
        override_password_prompt=lambda: None,
    )
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["subtotal_fils"] == 13_000  # 10000 item + 3000 installation fee


def test_record_remaining_payment_completes_invoice(conn):
    admin = get_admin(conn)
    invoice_id = invoice_service.create_installation_invoice(
        conn,
        admin,
        customer_name="أحمد",
        phone="33334444",
        area_region="المحرق",
        items=[{"description": "سجاد", "quantity": 1, "unit_price_fils": 20_000}],
        with_installation=False,
        deposit_fils=5_000,
        tax_included=False,
        override_password_prompt=lambda: None,
    )
    updated = invoice_service.record_remaining_payment(
        conn, admin, invoice_id, override_password_prompt=lambda: None
    )
    assert updated["header"]["status"] == "completed"
    total_paid = sum(p["amount_fils"] for p in updated["payments"])
    assert total_paid == updated["header"]["grand_total_fils"]


def test_record_remaining_payment_rejects_overpayment(conn):
    admin = get_admin(conn)
    invoice_id = invoice_service.create_installation_invoice(
        conn,
        admin,
        customer_name="أحمد",
        phone="33334444",
        area_region="المحرق",
        items=[{"description": "سجاد", "quantity": 1, "unit_price_fils": 20_000}],
        with_installation=False,
        deposit_fils=5_000,
        tax_included=False,
        override_password_prompt=lambda: None,
    )
    with pytest.raises(ValueError):
        invoice_service.record_remaining_payment(
            conn, admin, invoice_id, override_password_prompt=lambda: None, amount_fils=999_999
        )


def test_unprivileged_user_blocked_without_override(conn):
    from app.services.permission_service import PermissionDenied

    clerk_id = users_repo.create_user(conn, "clerk", "hash", "موظف")
    clerk = users_repo.get_user_by_id(conn, clerk_id)
    with pytest.raises(PermissionDenied):
        invoice_service.create_cash_invoice(
            conn,
            clerk,
            phone="33330000",
            items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
            tax_included=False,
            override_password_prompt=lambda: None,
        )
