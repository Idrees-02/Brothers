from datetime import date

from app.repositories import invoices_repo, reports_repo, vouchers_repo


def test_period_financial_summary(conn, admin_user_id):
    today = date.today().isoformat()

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
        subtotal_fils=10_000,
        tax_included=0,
        tax_rate_percent=10.0,
        tax_amount_fils=1_000,
        grand_total_fils=11_000,
        deposit_fils=0,
        created_by_user_id=admin_user_id,
    )
    conn.commit()

    vouchers_repo.insert_receipt(
        conn,
        voucher_no="REC-000001",
        description="دفعة زبون",
        amount_fils=5_000,
        receipt_date=today,
        created_by_user_id=admin_user_id,
    )
    vouchers_repo.insert_expense(
        conn,
        voucher_no="EXP-000001",
        description="كهرباء",
        amount_fils=3_000,
        expense_date=today,
        created_by_user_id=admin_user_id,
    )
    vouchers_repo.insert_purchase_invoice(
        conn,
        voucher_no="PUR-000001",
        supplier_name="مورد",
        total_amount_fils=2_000,
        purchase_date=today,
        created_by_user_id=admin_user_id,
    )
    conn.commit()

    summary = reports_repo.period_financial_summary(conn, today, today)
    assert summary["invoice_income_fils"] == 11_000
    assert summary["receipt_income_fils"] == 5_000
    assert summary["total_income_fils"] == 16_000
    assert summary["expense_fils"] == 3_000
    assert summary["purchase_fils"] == 2_000
    assert summary["total_expense_fils"] == 5_000
    assert summary["net_fils"] == 11_000


def test_period_transaction_ledger(conn, admin_user_id):
    today = date.today().isoformat()

    invoice_id = invoices_repo.insert_invoice(
        conn,
        invoice_type="installation",
        invoice_no="INST-000001",
        customer_name="أحمد",
        phone="33334444",
        address=None,
        area_region="المحرق",
        status="booked",
        with_installation=0,
        subtotal_fils=100_000,
        tax_included=0,
        tax_rate_percent=10.0,
        tax_amount_fils=10_000,
        grand_total_fils=110_000,
        deposit_fils=20_000,
        created_by_user_id=admin_user_id,
    )
    invoices_repo.insert_invoice_payment(conn, invoice_id, "deposit", 20_000, admin_user_id)
    invoices_repo.insert_invoice_payment(conn, invoice_id, "remaining", 90_000, admin_user_id)
    conn.commit()

    vouchers_repo.insert_receipt(
        conn,
        voucher_no="REC-000002",
        description="دفعة زبون",
        amount_fils=5_000,
        receipt_date=today,
        created_by_user_id=admin_user_id,
    )
    vouchers_repo.insert_expense(
        conn,
        voucher_no="EXP-000002",
        description="كهرباء",
        amount_fils=3_000,
        expense_date=today,
        created_by_user_id=admin_user_id,
    )
    conn.commit()

    ledger = reports_repo.period_transaction_ledger(conn, today, today)
    kinds = [r["kind"] for r in ledger]
    assert kinds.count("invoice") == 1
    assert kinds.count("remaining_payment") == 1
    assert kinds.count("expense") == 1
    assert kinds.count("receipt") == 1
    # deposit payments happen at creation time and aren't shown separately -
    # only later remaining-balance collections get their own ledger row
    assert kinds.count("deposit") == 0

    invoice_record = next(r for r in ledger if r["kind"] == "invoice")
    assert invoice_record["reference"] == "INST-000001"
    assert invoice_record["amount_fils"] == 110_000

    remaining_record = next(r for r in ledger if r["kind"] == "remaining_payment")
    assert remaining_record["amount_fils"] == 90_000
