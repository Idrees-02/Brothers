from app.repositories import invoices_repo, reports_repo


def test_tax_report_summary_excludes_voided(conn, admin_user_id):
    active_id = invoices_repo.insert_invoice(
        conn,
        invoice_type="cash",
        invoice_no="CASH-000001",
        customer_name="نقدي",
        phone="33330000",
        address=None,
        area_region=None,
        status="completed",
        with_installation=None,
        subtotal_fils=10_000,
        tax_included=0,
        tax_rate_percent=10.0,
        tax_amount_fils=1_000,
        grand_total_fils=11_000,
        deposit_fils=0,
        created_by_user_id=admin_user_id,
    )
    voided_id = invoices_repo.insert_invoice(
        conn,
        invoice_type="cash",
        invoice_no="CASH-000002",
        customer_name="نقدي",
        phone="33331111",
        address=None,
        area_region=None,
        status="completed",
        with_installation=None,
        subtotal_fils=5_000,
        tax_included=0,
        tax_rate_percent=10.0,
        tax_amount_fils=500,
        grand_total_fils=5_500,
        deposit_fils=0,
        created_by_user_id=admin_user_id,
    )
    invoices_repo.void_invoice(conn, voided_id, admin_user_id)
    conn.commit()

    from datetime import date

    today = date.today().isoformat()
    summary = reports_repo.tax_report_summary(conn, today, today)
    assert summary["invoice_count"] == 1
    assert summary["total_tax_fils"] == 1_000
    assert summary["total_grand_fils"] == 11_000
