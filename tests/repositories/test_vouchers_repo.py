from app.repositories import vouchers_repo


def test_expense_create_and_void(conn, admin_user_id):
    expense_id = vouchers_repo.insert_expense(
        conn,
        voucher_no="EXP-000001",
        description="كهرباء",
        amount_fils=20_000,
        expense_date="2026-07-01",
        created_by_user_id=admin_user_id,
    )
    active = vouchers_repo.list_expenses(conn)
    assert len(active) == 1

    vouchers_repo.void_expense(conn, expense_id, admin_user_id)
    active_after_void = vouchers_repo.list_expenses(conn)
    assert active_after_void == []


def test_receipt_create_and_void(conn, admin_user_id):
    receipt_id = vouchers_repo.insert_receipt(
        conn,
        voucher_no="REC-000001",
        description="دفعة نقدية من زبون",
        amount_fils=15_000,
        receipt_date="2026-07-01",
        created_by_user_id=admin_user_id,
    )
    active = vouchers_repo.list_receipts(conn)
    assert len(active) == 1
    assert active[0]["id"] == receipt_id

    vouchers_repo.void_receipt(conn, receipt_id, admin_user_id)
    assert vouchers_repo.list_receipts(conn) == []


def test_purchase_invoice_with_items(conn, admin_user_id):
    purchase_id = vouchers_repo.insert_purchase_invoice(
        conn,
        voucher_no="PUR-000001",
        supplier_name="مورد السجاد",
        total_amount_fils=100_000,
        purchase_date="2026-07-01",
        created_by_user_id=admin_user_id,
    )
    vouchers_repo.insert_purchase_invoice_item(
        conn, purchase_id, "لفة سجاد", 10, 10_000, 100_000
    )
    conn.commit()

    fetched = vouchers_repo.get_purchase_invoice(conn, purchase_id)
    assert fetched["header"]["supplier_name"] == "مورد السجاد"
    assert len(fetched["items"]) == 1
