from datetime import date

from app.repositories import invoices_repo, reports_repo, vouchers_repo


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

    today = date.today().isoformat()
    summary = reports_repo.tax_report_summary(conn, today, today)
    assert summary["sales_count"] == 1
    assert summary["sales_tax_fils"] == 1_000
    assert summary["sales_total_fils"] == 11_000
    assert summary["net_tax_fils"] == 1_000


def test_tax_report_summary_includes_purchases_and_nets_tax(conn, admin_user_id):
    invoices_repo.insert_invoice(
        conn,
        invoice_type="cash",
        invoice_no="CASH-000001",
        customer_name="نقدي",
        phone="33330000",
        address=None,
        area_region=None,
        status="completed",
        with_installation=None,
        subtotal_fils=200_000,
        tax_included=0,
        tax_rate_percent=10.0,
        tax_amount_fils=20_000,
        grand_total_fils=220_000,
        deposit_fils=0,
        created_by_user_id=admin_user_id,
    )
    vouchers_repo.insert_purchase_invoice(
        conn,
        voucher_no="PUR-000001",
        supplier_name="مورد",
        total_amount_fils=55_000,
        subtotal_fils=50_000,
        tax_included=0,
        tax_rate_percent=10.0,
        tax_amount_fils=5_000,
        purchase_date=date.today().isoformat(),
        created_by_user_id=admin_user_id,
    )
    conn.commit()

    today = date.today().isoformat()
    summary = reports_repo.tax_report_summary(conn, today, today)
    assert summary["sales_subtotal_fils"] == 200_000
    assert summary["sales_tax_fils"] == 20_000
    assert summary["sales_total_fils"] == 220_000
    assert summary["purchases_subtotal_fils"] == 50_000
    assert summary["purchases_tax_fils"] == 5_000
    assert summary["purchases_total_fils"] == 55_000
    assert summary["net_tax_fils"] == 15_000
