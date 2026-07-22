"""SQL access for the chart of accounts (الصندوق النقدي / البنك / المالك /
...) and per-account balances/transaction history for سندات الصرف والقبض."""

import sqlite3


def create_account(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("INSERT INTO accounts (name) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid


def list_accounts(conn: sqlite3.Connection, include_inactive: bool = False) -> list[sqlite3.Row]:
    if include_inactive:
        return conn.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    return conn.execute("SELECT * FROM accounts WHERE is_active = 1 ORDER BY name").fetchall()


def get_account(conn: sqlite3.Connection, account_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()


def set_active(conn: sqlite3.Connection, account_id: int, is_active: bool) -> None:
    conn.execute("UPDATE accounts SET is_active = ? WHERE id = ?", (int(is_active), account_id))
    conn.commit()


def account_balance_fils(conn: sqlite3.Connection, account_id: int) -> int:
    received = conn.execute(
        "SELECT COALESCE(SUM(amount_fils), 0) FROM receipts WHERE account_id = ? AND voided_at IS NULL",
        (account_id,),
    ).fetchone()[0]
    paid_out = conn.execute(
        "SELECT COALESCE(SUM(amount_fils), 0) FROM expenses WHERE account_id = ? AND voided_at IS NULL",
        (account_id,),
    ).fetchone()[0]
    return received - paid_out


def account_transactions(conn: sqlite3.Connection, account_id: int) -> list[dict]:
    """Unified, date-sorted ledger for one account: receipts credit it,
    expenses debit it."""
    receipts = conn.execute(
        """SELECT 'receipt' AS kind, voucher_no, description, amount_fils,
                  receipt_date AS txn_date, created_at
           FROM receipts WHERE account_id = ? AND voided_at IS NULL""",
        (account_id,),
    ).fetchall()
    expenses = conn.execute(
        """SELECT 'expense' AS kind, voucher_no, description, amount_fils,
                  expense_date AS txn_date, created_at
           FROM expenses WHERE account_id = ? AND voided_at IS NULL""",
        (account_id,),
    ).fetchall()
    combined = [dict(row) for row in receipts] + [dict(row) for row in expenses]
    combined.sort(key=lambda row: (row["txn_date"], row["created_at"]))
    return combined
