"""Aggregate queries for the tax report (كشف ضريبي)."""

import sqlite3


def tax_report_summary(conn: sqlite3.Connection, start_date: str, end_date: str) -> sqlite3.Row:
    return conn.execute(
        """SELECT
               COALESCE(SUM(subtotal_fils), 0) AS total_subtotal_fils,
               COALESCE(SUM(tax_amount_fils), 0) AS total_tax_fils,
               COALESCE(SUM(grand_total_fils), 0) AS total_grand_fils,
               COUNT(*) AS invoice_count
           FROM invoices
           WHERE status != 'voided' AND date(created_at) BETWEEN date(?) AND date(?)""",
        (start_date, end_date),
    ).fetchone()


def tax_report_invoices(conn: sqlite3.Connection, start_date: str, end_date: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT invoice_no, invoice_type, customer_name, subtotal_fils, tax_rate_percent,
                  tax_included, tax_amount_fils, grand_total_fils, created_at
           FROM invoices
           WHERE status != 'voided' AND date(created_at) BETWEEN date(?) AND date(?)
           ORDER BY created_at""",
        (start_date, end_date),
    ).fetchall()
