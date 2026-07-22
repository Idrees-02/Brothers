from app.repositories import accounts_repo, users_repo, vouchers_repo
from app.services import voucher_service


def get_admin(conn):
    return users_repo.get_user_by_username(conn, "admin")


def get_cash_account_id(conn):
    return accounts_repo.list_accounts(conn)[0]["id"]


def test_create_expense(conn):
    admin = get_admin(conn)
    account_id = get_cash_account_id(conn)
    expense_id = voucher_service.create_expense(
        conn, admin, "كهرباء", 20_000, "2026-07-01", account_id, override_password_prompt=lambda: None
    )
    rows = vouchers_repo.list_expenses(conn)
    assert len(rows) == 1
    assert rows[0]["id"] == expense_id
    assert rows[0]["voucher_no"] == "E-1"
    assert rows[0]["account_id"] == account_id


def test_create_receipt(conn):
    admin = get_admin(conn)
    account_id = get_cash_account_id(conn)
    receipt_id = voucher_service.create_receipt(
        conn, admin, "دفعة من زبون", 15_000, "2026-07-01", account_id, override_password_prompt=lambda: None
    )
    rows = vouchers_repo.list_receipts(conn)
    assert len(rows) == 1
    assert rows[0]["id"] == receipt_id
    assert rows[0]["voucher_no"] == "R-1"
    assert rows[0]["account_id"] == account_id


def test_create_expense_rejects_invalid_account(conn):
    import pytest

    admin = get_admin(conn)
    with pytest.raises(ValueError):
        voucher_service.create_expense(
            conn, admin, "كهرباء", 20_000, "2026-07-01", 999_999, override_password_prompt=lambda: None
        )


def test_create_purchase_invoice_computes_total(conn):
    admin = get_admin(conn)
    purchase_id = voucher_service.create_purchase_invoice(
        conn,
        admin,
        supplier_name="مورد السجاد",
        purchase_date="2026-07-01",
        items=[
            {"description": "لفة سجاد", "quantity": 10, "unit_price_fils": 10_000},
            {"description": "لاصق", "quantity": 2, "unit_price_fils": 1_500},
        ],
        override_password_prompt=lambda: None,
    )
    fetched = vouchers_repo.get_purchase_invoice(conn, purchase_id)
    assert fetched["header"]["subtotal_fils"] == 103_000
    # Default settings apply a 10% tax on top when tax_included isn't passed.
    assert fetched["header"]["tax_amount_fils"] == 10_300
    assert fetched["header"]["total_amount_fils"] == 113_300
    assert len(fetched["items"]) == 2


def test_create_purchase_invoice_tax_included(conn):
    admin = get_admin(conn)
    purchase_id = voucher_service.create_purchase_invoice(
        conn,
        admin,
        supplier_name="مورد السجاد",
        purchase_date="2026-07-01",
        items=[{"description": "لفة سجاد", "quantity": 1, "unit_price_fils": 11_000}],
        override_password_prompt=lambda: None,
        tax_included=True,
    )
    fetched = vouchers_repo.get_purchase_invoice(conn, purchase_id)
    assert fetched["header"]["total_amount_fils"] == 11_000
    assert fetched["header"]["tax_amount_fils"] == 1_000
