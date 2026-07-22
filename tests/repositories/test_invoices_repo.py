from app.repositories import invoices_repo


def _make_installation_invoice(conn, admin_user_id, deposit_fils=5_000, grand_total_fils=20_000):
    invoice_id = invoices_repo.insert_invoice(
        conn,
        invoice_type="installation",
        invoice_no="INST-000001",
        customer_name="أحمد",
        phone="33334444",
        address=None,
        area_region="المحرق",
        status="booked",
        with_installation=1,
        subtotal_fils=18_182,
        tax_included=0,
        tax_rate_percent=10.0,
        tax_amount_fils=1_818,
        grand_total_fils=grand_total_fils,
        deposit_fils=deposit_fils,
        created_by_user_id=admin_user_id,
    )
    invoices_repo.insert_invoice_item(
        conn, invoice_id, "سجاد مقاس خاص", 5.0, "sqm", 3_636, 18_182
    )
    invoices_repo.insert_invoice_payment(conn, invoice_id, "deposit", deposit_fils, admin_user_id)
    conn.commit()
    return invoice_id


def test_create_installation_invoice_round_trip(conn, admin_user_id):
    invoice_id = _make_installation_invoice(conn, admin_user_id)

    fetched = invoices_repo.get_invoice(conn, invoice_id)
    assert fetched["header"]["status"] == "booked"
    assert fetched["header"]["deposit_fils"] == 5_000
    assert len(fetched["items"]) == 1
    assert len(fetched["payments"]) == 1
    assert fetched["payments"][0]["payment_type"] == "deposit"


def test_record_remaining_payment_and_complete(conn, admin_user_id):
    invoice_id = _make_installation_invoice(conn, admin_user_id)

    invoices_repo.insert_invoice_payment(conn, invoice_id, "remaining", 15_000, admin_user_id)
    invoices_repo.set_invoice_status(conn, invoice_id, "completed")
    conn.commit()

    fetched = invoices_repo.get_invoice(conn, invoice_id)
    assert fetched["header"]["status"] == "completed"
    total_paid = sum(p["amount_fils"] for p in fetched["payments"])
    assert total_paid == fetched["header"]["grand_total_fils"]


def test_search_invoices_by_phone_and_name(conn, admin_user_id):
    _make_installation_invoice(conn, admin_user_id)

    by_phone = invoices_repo.search_invoices(conn, "3333")
    by_name = invoices_repo.search_invoices(conn, "أحمد")
    by_no_match = invoices_repo.search_invoices(conn, "nonexistent")

    assert len(by_phone) == 1
    assert len(by_name) == 1
    assert by_no_match == []


def test_void_invoice_excluded_from_range_query(conn, admin_user_id):
    invoice_id = _make_installation_invoice(conn, admin_user_id)
    invoices_repo.void_invoice(conn, invoice_id, admin_user_id)
    conn.commit()

    from datetime import date

    today = date.today().isoformat()
    active = invoices_repo.list_invoices_between(conn, today, today, exclude_voided=True)
    all_rows = invoices_repo.list_invoices_between(conn, today, today, exclude_voided=False)
    assert active == []
    assert len(all_rows) == 1
    assert all_rows[0]["status"] == "voided"


def test_count_invoices_created_on(conn, admin_user_id):
    from datetime import date

    today = date.today().isoformat()
    _make_installation_invoice(conn, admin_user_id)
    assert invoices_repo.count_invoices_created_on(conn, today) == 1
    assert invoices_repo.count_invoices_created_on(conn, "2000-01-01") == 0


def test_list_all_invoices(conn, admin_user_id):
    _make_installation_invoice(conn, admin_user_id)
    assert len(invoices_repo.list_all_invoices(conn)) == 1


def test_installation_scheduling_for_date(conn, admin_user_id):
    from datetime import date

    today = date.today().isoformat()
    invoice_id = invoices_repo.insert_invoice(
        conn,
        invoice_type="installation",
        invoice_no="INST-000002",
        customer_name="سالم",
        phone="33335555",
        address=None,
        area_region="الرفاع",
        status="booked",
        with_installation=1,
        subtotal_fils=10_000,
        tax_included=0,
        tax_rate_percent=10.0,
        tax_amount_fils=1_000,
        grand_total_fils=11_000,
        deposit_fils=0,
        installation_date=today,
        installation_status="pending",
        created_by_user_id=admin_user_id,
    )
    conn.commit()

    assert invoices_repo.count_installations_for_date(conn, today) == 1
    due_today = invoices_repo.list_installations_for_date(conn, today)
    assert len(due_today) == 1
    assert due_today[0]["id"] == invoice_id
    assert due_today[0]["assigned_employee_name"] is None

    from app.repositories import employees_repo

    employee_id = employees_repo.create_employee(conn, "محمد", 300_000)
    invoices_repo.assign_installer(conn, invoice_id, employee_id)
    due_today = invoices_repo.list_installations_for_date(conn, today)
    assert due_today[0]["assigned_employee_name"] == "محمد"

    invoices_repo.set_installation_status(conn, invoice_id, "installed")
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["installation_status"] == "installed"

    invoices_repo.set_installation_status(conn, invoice_id, "pending", installation_date="2026-08-01")
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["installation_date"] == "2026-08-01"
    assert invoices_repo.count_installations_for_date(conn, today) == 0

    invoices_repo.clear_installation_date(conn, invoice_id)
    header = invoices_repo.get_invoice(conn, invoice_id)["header"]
    assert header["installation_date"] is None
    assert header["installation_status"] == "postponed"
