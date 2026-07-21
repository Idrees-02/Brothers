from app.repositories import users_repo, vouchers_repo
from app.services import voucher_service


def get_admin(conn):
    return users_repo.get_user_by_username(conn, "admin")


def test_create_expense(conn):
    admin = get_admin(conn)
    expense_id = voucher_service.create_expense(
        conn, admin, "كهرباء", 20_000, "2026-07-01", override_password_prompt=lambda: None
    )
    rows = vouchers_repo.list_expenses(conn)
    assert len(rows) == 1
    assert rows[0]["id"] == expense_id
    assert rows[0]["voucher_no"] == "EXP-000001"


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
    assert fetched["header"]["total_amount_fils"] == 103_000
    assert len(fetched["items"]) == 2
