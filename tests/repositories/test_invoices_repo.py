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
