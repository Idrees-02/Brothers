"""Aggregate queries for the tax report (كشف ضريبي) and the combined
income/expense financial report (daily/weekly/monthly)."""

import sqlite3


def tax_report_summary(conn: sqlite3.Connection, start_date: str, end_date: str) -> dict:
    """Sales-side and purchases-side tax totals for the period, plus the net
    tax payable (tax collected on sales minus tax paid on purchases) - the
    basis of the tax report screen (كشف ضريبي)."""
    sales = conn.execute(
        """SELECT
               COALESCE(SUM(subtotal_fils), 0) AS subtotal_fils,
               COALESCE(SUM(tax_amount_fils), 0) AS tax_fils,
               COALESCE(SUM(grand_total_fils), 0) AS total_fils,
               COUNT(*) AS count
           FROM invoices
           WHERE status != 'voided' AND date(created_at) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchone()
    purchases = conn.execute(
        """SELECT
               COALESCE(SUM(subtotal_fils), 0) AS subtotal_fils,
               COALESCE(SUM(tax_amount_fils), 0) AS tax_fils,
               COALESCE(SUM(total_amount_fils), 0) AS total_fils,
               COUNT(*) AS count
           FROM purchase_invoices
           WHERE voided_at IS NULL AND date(purchase_date) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchone()
    return {
        "sales_count": sales["count"],
        "sales_subtotal_fils": sales["subtotal_fils"],
        "sales_tax_fils": sales["tax_fils"],
        "sales_total_fils": sales["total_fils"],
        "purchases_count": purchases["count"],
        "purchases_subtotal_fils": purchases["subtotal_fils"],
        "purchases_tax_fils": purchases["tax_fils"],
        "purchases_total_fils": purchases["total_fils"],
        "net_tax_fils": sales["tax_fils"] - purchases["tax_fils"],
    }


def tax_report_invoices(conn: sqlite3.Connection, start_date: str, end_date: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT invoice_no, invoice_type, customer_name, subtotal_fils, tax_rate_percent,
                  tax_included, tax_amount_fils, grand_total_fils, created_at
           FROM invoices
           WHERE status != 'voided' AND date(created_at) BETWEEN date(?) AND date(?)
           ORDER BY created_at""",
        (start_date, end_date),
    ).fetchall()


def tax_report_purchases(conn: sqlite3.Connection, start_date: str, end_date: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT voucher_no, supplier_name, subtotal_fils, tax_rate_percent,
                  tax_included, tax_amount_fils, total_amount_fils, purchase_date
           FROM purchase_invoices
           WHERE voided_at IS NULL AND date(purchase_date) BETWEEN date(?) AND date(?)
           ORDER BY purchase_date""",
        (start_date, end_date),
    ).fetchall()


def _sum_fils(conn: sqlite3.Connection, sql: str, start_date: str, end_date: str) -> int:
    row = conn.execute(sql, (start_date, end_date)).fetchone()
    return row[0] or 0


def period_financial_summary(conn: sqlite3.Connection, start_date: str, end_date: str) -> dict:
    """Combined income vs. expense summary for a date range - the basis of
    the daily/weekly/monthly financial report screen.

    Credit (آجل) invoices are cash-basis: a credit sales invoice counts only
    through the payments actually received on it (by payment date), and a
    credit purchase invoice counts only once settled (by its paid_at date) -
    an unpaid credit invoice never inflates the report."""
    invoice_income_fils = _sum_fils(
        conn,
        """SELECT COALESCE(SUM(grand_total_fils), 0) FROM invoices
           WHERE status != 'voided' AND is_credit = 0
             AND date(created_at) BETWEEN date(?) AND date(?)""",
        start_date,
        end_date,
    )
    invoice_income_fils += _sum_fils(
        conn,
        """SELECT COALESCE(SUM(invoice_payments.amount_fils), 0)
           FROM invoice_payments
           JOIN invoices ON invoices.id = invoice_payments.invoice_id
           WHERE invoices.status != 'voided' AND invoices.is_credit = 1
             AND date(invoice_payments.paid_at) BETWEEN date(?) AND date(?)""",
        start_date,
        end_date,
    )
    receipt_income_fils = _sum_fils(
        conn,
        """SELECT COALESCE(SUM(amount_fils), 0) FROM receipts
           WHERE voided_at IS NULL AND date(receipt_date) BETWEEN date(?) AND date(?)""",
        start_date,
        end_date,
    )
    expense_fils = _sum_fils(
        conn,
        """SELECT COALESCE(SUM(amount_fils), 0) FROM expenses
           WHERE voided_at IS NULL AND date(expense_date) BETWEEN date(?) AND date(?)""",
        start_date,
        end_date,
    )
    purchase_fils = _sum_fils(
        conn,
        """SELECT COALESCE(SUM(total_amount_fils), 0) FROM purchase_invoices
           WHERE voided_at IS NULL AND is_credit = 0
             AND date(purchase_date) BETWEEN date(?) AND date(?)""",
        start_date,
        end_date,
    )
    purchase_fils += _sum_fils(
        conn,
        """SELECT COALESCE(SUM(total_amount_fils), 0) FROM purchase_invoices
           WHERE voided_at IS NULL AND is_credit = 1 AND paid_at IS NOT NULL
             AND date(paid_at) BETWEEN date(?) AND date(?)""",
        start_date,
        end_date,
    )
    total_income_fils = invoice_income_fils + receipt_income_fils
    total_expense_fils = expense_fils + purchase_fils
    return {
        "invoice_income_fils": invoice_income_fils,
        "receipt_income_fils": receipt_income_fils,
        "total_income_fils": total_income_fils,
        "expense_fils": expense_fils,
        "purchase_fils": purchase_fils,
        "total_expense_fils": total_expense_fils,
        "net_fils": total_income_fils - total_expense_fils,
    }


def period_transaction_ledger(conn: sqlite3.Connection, start_date: str, end_date: str) -> list[dict]:
    """Record-by-record journal for the financial report: every invoice
    created, every later remaining-balance collection, every expense,
    receipt, and purchase invoice in the period - each with its own amount
    and details, not just totals."""
    records: list[dict] = []

    for row in conn.execute(
        """SELECT invoice_no, customer_name, grand_total_fils, created_at
           FROM invoices
           WHERE status != 'voided' AND is_credit = 0
             AND date(created_at) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchall():
        records.append(
            {
                "kind": "invoice",
                "reference": row["invoice_no"],
                "description": row["customer_name"] or "",
                "amount_fils": row["grand_total_fils"],
                "txn_date": row["created_at"],
            }
        )

    for row in conn.execute(
        """SELECT invoices.invoice_no, invoices.is_credit,
                  invoice_payments.payment_type, invoice_payments.amount_fils,
                  invoice_payments.paid_at
           FROM invoice_payments
           JOIN invoices ON invoices.id = invoice_payments.invoice_id
           WHERE invoices.status != 'voided'
             AND (invoice_payments.payment_type = 'remaining' OR invoices.is_credit = 1)
             AND date(invoice_payments.paid_at) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchall():
        records.append(
            {
                "kind": "remaining_payment",
                "reference": row["invoice_no"],
                "description": "سداد فاتورة آجلة" if row["is_credit"] else "سداد متبقي",
                "amount_fils": row["amount_fils"],
                "txn_date": row["paid_at"],
            }
        )

    for row in conn.execute(
        """SELECT expenses.voucher_no, expenses.description, expenses.amount_fils,
                  expenses.expense_date, accounts.name AS account_name
           FROM expenses
           LEFT JOIN accounts ON accounts.id = expenses.account_id
           WHERE expenses.voided_at IS NULL
             AND date(expenses.expense_date) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchall():
        records.append(
            {
                "kind": "expense",
                "reference": row["voucher_no"],
                "description": f"{row['description']} - {row['account_name'] or ''}",
                "amount_fils": row["amount_fils"],
                "txn_date": row["expense_date"],
            }
        )

    for row in conn.execute(
        """SELECT receipts.voucher_no, receipts.description, receipts.amount_fils,
                  receipts.receipt_date, accounts.name AS account_name
           FROM receipts
           LEFT JOIN accounts ON accounts.id = receipts.account_id
           WHERE receipts.voided_at IS NULL
             AND date(receipts.receipt_date) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchall():
        records.append(
            {
                "kind": "receipt",
                "reference": row["voucher_no"],
                "description": f"{row['description']} - {row['account_name'] or ''}",
                "amount_fils": row["amount_fils"],
                "txn_date": row["receipt_date"],
            }
        )

    for row in conn.execute(
        """SELECT voucher_no, supplier_name, total_amount_fils, purchase_date
           FROM purchase_invoices
           WHERE voided_at IS NULL AND is_credit = 0
             AND date(purchase_date) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchall():
        records.append(
            {
                "kind": "purchase",
                "reference": row["voucher_no"],
                "description": row["supplier_name"],
                "amount_fils": row["total_amount_fils"],
                "txn_date": row["purchase_date"],
            }
        )

    # Credit purchases enter the ledger on the day they were settled, not
    # the day they were recorded.
    for row in conn.execute(
        """SELECT voucher_no, supplier_name, total_amount_fils, paid_at
           FROM purchase_invoices
           WHERE voided_at IS NULL AND is_credit = 1 AND paid_at IS NOT NULL
             AND date(paid_at) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchall():
        records.append(
            {
                "kind": "purchase",
                "reference": row["voucher_no"],
                "description": f"{row['supplier_name']} (تسديد فاتورة آجلة)",
                "amount_fils": row["total_amount_fils"],
                "txn_date": row["paid_at"],
            }
        )

    records.sort(key=lambda r: r["txn_date"])
    return records
