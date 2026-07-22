from app.repositories import accounts_repo, vouchers_repo


def test_default_accounts_seeded(conn):
    accounts = accounts_repo.list_accounts(conn)
    names = {a["name"] for a in accounts}
    assert "الصندوق النقدي" in names
    assert "البنك" in names
    assert "المالك" in names


def test_create_and_deactivate_account(conn):
    account_id = accounts_repo.create_account(conn, "حساب تجريبي")
    assert any(a["id"] == account_id for a in accounts_repo.list_accounts(conn))

    accounts_repo.set_active(conn, account_id, False)
    assert not any(a["id"] == account_id for a in accounts_repo.list_accounts(conn))
    assert any(a["id"] == account_id for a in accounts_repo.list_accounts(conn, include_inactive=True))


def test_account_balance_and_transactions(conn, admin_user_id):
    account_id = accounts_repo.create_account(conn, "الصندوق التجريبي")

    vouchers_repo.insert_receipt(
        conn,
        voucher_no="REC-000001",
        description="دفعة من زبون",
        amount_fils=50_000,
        receipt_date="2026-07-01",
        account_id=account_id,
        created_by_user_id=admin_user_id,
    )
    vouchers_repo.insert_expense(
        conn,
        voucher_no="EXP-000001",
        description="فاتورة كهرباء",
        amount_fils=15_000,
        expense_date="2026-07-02",
        account_id=account_id,
        created_by_user_id=admin_user_id,
    )

    assert accounts_repo.account_balance_fils(conn, account_id) == 35_000

    transactions = accounts_repo.account_transactions(conn, account_id)
    assert len(transactions) == 2
    assert transactions[0]["kind"] == "receipt"
    assert transactions[1]["kind"] == "expense"
