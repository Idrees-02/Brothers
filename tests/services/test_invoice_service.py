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
        payment_method="cash",
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
            payment_method="cash",
            override_password_prompt=lambda: None,
        )


def test_create_cash_invoice_with_delivery_requires_region(conn):
    admin = get_admin(conn)
    with pytest.raises(ValueError):
        invoice_service.create_cash_invoice(
            conn,
            admin,
            phone="33330000",
            items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
            tax_included=False,
            payment_method="cash",
            override_password_prompt=lambda: None,
            with_delivery=True,
        )


def test_create_cash_invoice_with_delivery(conn):
    admin = get_admin(conn)
    invoice_id = invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="33330000",
        items=[
            {"description": "سجادة", "quantity": 1, "unit_price_fils": 50_000},
            {"description": "رسوم التوصيل", "quantity": 1, "unit_price_fils": 5_000},
        ],
        tax_included=False,
        payment_method="cash",
        override_password_prompt=lambda: None,
        with_delivery=True,
        area_region="المنامة",
        address="شارع 10",
        deposit_fils=10_000,
        delivery_date="2026-08-01",
    )
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["with_delivery"] == 1
    assert header["area_region"] == "المنامة"
    assert header["address"] == "شارع 10"
    assert header["installation_date"] == "2026-08-01"
    assert header["installation_status"] == "pending"
    assert header["deposit_fils"] == 10_000
    assert header["status"] == "booked"  # deposit < grand total

    # It must appear in the shared installation-schedule query for that date.
    scheduled = invoice_service.list_installations_for_date(conn, "2026-08-01")
    assert len(scheduled) == 1
    assert scheduled[0]["id"] == invoice_id


def test_create_cash_invoice_without_delivery_ignores_delivery_fields(conn):
    admin = get_admin(conn)
    invoice_id = invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="33330000",
        items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
        tax_included=False,
        payment_method="cash",
        override_password_prompt=lambda: None,
        area_region="يجب أن يُتجاهل",  # with_delivery=False - these must not persist
    )
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["with_delivery"] == 0
    assert header["area_region"] is None
    assert header["deposit_fils"] == 0
    assert header["status"] == "completed"


def test_create_cash_invoice_partial_deposit_without_delivery_stays_booked(conn):
    """A deposit can now be recorded on a plain cash invoice (no delivery) -
    the invoice stays booked with the deposit as its only payment until the
    remainder is collected."""
    admin = get_admin(conn)
    invoice_id = invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="33330000",
        items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
        tax_included=False,
        payment_method="cash",
        override_password_prompt=lambda: None,
        deposit_fils=5_000,
    )
    invoice = invoices_repo.get_invoice(conn, invoice_id)
    header = invoice["header"]
    assert header["with_delivery"] == 0
    assert header["deposit_fils"] == 5_000
    assert header["status"] == "booked"
    assert [p["payment_type"] for p in invoice["payments"]] == ["deposit"]
    assert sum(p["amount_fils"] for p in invoice["payments"]) == 5_000


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
        payment_method="cash",
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
            payment_method="cash",
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
        payment_method="cash",
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
        payment_method="cash",
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
        payment_method="cash",
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
            payment_method="cash",
            override_password_prompt=lambda: None,
        )


def _create_scheduled_installation(conn, admin, installation_date):
    from app.repositories import employees_repo

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
        payment_method="cash",
        override_password_prompt=lambda: None,
        installation_date=installation_date,
    )
    employee_id = employees_repo.create_employee(conn, "محمد", 300_000)
    return invoice_id, employee_id


def test_create_installation_invoice_sets_installation_date_and_pending_status(conn):
    admin = get_admin(conn)
    invoice_id, _ = _create_scheduled_installation(conn, admin, "2026-08-01")
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["installation_date"] == "2026-08-01"
    assert header["installation_status"] == "pending"


def test_assign_installer_and_list_for_date(conn):
    admin = get_admin(conn)
    invoice_id, employee_id = _create_scheduled_installation(conn, admin, "2026-08-01")

    invoice_service.assign_installer(
        conn, admin, invoice_id, employee_id, override_password_prompt=lambda: None
    )
    due = invoice_service.list_installations_for_date(conn, "2026-08-01")
    assert len(due) == 1
    assert due[0]["assigned_employee_name"] == "محمد"


def test_mark_installed(conn):
    admin = get_admin(conn)
    invoice_id, _ = _create_scheduled_installation(conn, admin, "2026-08-01")
    invoice_service.mark_installed(conn, admin, invoice_id, override_password_prompt=lambda: None)
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["installation_status"] == "installed"


def test_postpone_with_new_date_reschedules(conn):
    admin = get_admin(conn)
    invoice_id, _ = _create_scheduled_installation(conn, admin, "2026-08-01")
    invoice_service.postpone_installation(
        conn, admin, invoice_id, override_password_prompt=lambda: None,
        new_installation_date="2026-08-05",
    )
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["installation_date"] == "2026-08-05"
    assert header["installation_status"] == "pending"
    assert invoice_service.list_installations_for_date(conn, "2026-08-01") == []
    assert len(invoice_service.list_installations_for_date(conn, "2026-08-05")) == 1


def test_postpone_without_date_clears_schedule(conn):
    admin = get_admin(conn)
    invoice_id, _ = _create_scheduled_installation(conn, admin, "2026-08-01")
    invoice_service.postpone_installation(
        conn, admin, invoice_id, override_password_prompt=lambda: None
    )
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["installation_date"] is None
    assert header["installation_status"] == "postponed"


def test_cancel_installation(conn):
    admin = get_admin(conn)
    invoice_id, _ = _create_scheduled_installation(conn, admin, "2026-08-01")
    invoice_service.cancel_installation(conn, admin, invoice_id, override_password_prompt=lambda: None)
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["installation_status"] == "cancelled"
    # cancelling the installation appointment does not void the invoice financially
    assert header["status"] != "voided"


def test_list_all_invoices(conn):
    admin = get_admin(conn)
    _create_scheduled_installation(conn, admin, "2026-08-01")
    assert len(invoice_service.list_all_invoices(conn)) == 1


def test_update_invoice_recomputes_totals_with_original_rate(conn):
    from app.repositories import settings_repo

    admin = get_admin(conn)
    invoice_id = invoice_service.create_cash_invoice(
        conn,
        admin,
        phone="33330000",
        items=[{"description": "سجادة", "quantity": 1, "unit_price_fils": 10_000}],
        tax_included=False,
        payment_method="cash",
        override_password_prompt=lambda: None,
    )
    # change the global rate after creation - editing must keep the invoice's own rate
    settings_repo.update_settings(conn, tax_rate_percent=20.0)

    updated = invoice_service.update_invoice(
        conn,
        admin,
        invoice_id,
        phone="33339999",
        items=[{"description": "سجادة كبيرة", "quantity": 2, "unit_price_fils": 15_000}],
        tax_included=False,
        payment_method="cash",
        override_password_prompt=lambda: None,
        customer_name="خالد",
    )
    header = updated["header"]
    assert header["phone"] == "33339999"
    assert header["customer_name"] == "خالد"
    assert header["subtotal_fils"] == 30_000
    assert header["tax_rate_percent"] == 10.0  # unchanged from creation time
    assert header["tax_amount_fils"] == 3_000
    assert header["grand_total_fils"] == 33_000
    assert len(updated["items"]) == 1
    assert updated["items"][0]["description"] == "سجادة كبيرة"


def test_update_invoice_rejects_total_below_amount_paid(conn):
    admin = get_admin(conn)
    invoice_id, _ = _create_scheduled_installation(conn, admin, "2026-08-01")  # deposit 5_000 paid
    with pytest.raises(ValueError):
        invoice_service.update_invoice(
            conn,
            admin,
            invoice_id,
            phone="33334444",
            items=[{"description": "سجاد صغير", "quantity": 1, "unit_price_fils": 1_000}],
            tax_included=False,
            payment_method="cash",
            override_password_prompt=lambda: None,
            customer_name="أحمد",
            area_region="المحرق",
        )


def test_update_invoice_requires_area_region_for_installation(conn):
    admin = get_admin(conn)
    invoice_id, _ = _create_scheduled_installation(conn, admin, "2026-08-01")
    with pytest.raises(ValueError):
        invoice_service.update_invoice(
            conn,
            admin,
            invoice_id,
            phone="33334444",
            items=[{"description": "سجاد", "quantity": 1, "unit_price_fils": 20_000}],
            tax_included=False,
            payment_method="cash",
            override_password_prompt=lambda: None,
            customer_name="أحمد",
            area_region="",
        )
