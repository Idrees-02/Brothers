"""Expense vouchers (سندات صرف) and purchase invoices (فواتير شراء)."""

import sqlite3

from app.domain.invoice_calc import line_total_fils, sum_line_items_fils
from app.domain.permissions import Permission
from app.repositories import settings_repo, vouchers_repo
from app.services.permission_service import OverridePrompt, require_permission


def create_expense(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    description: str,
    amount_fils: int,
    expense_date: str,
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> int:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "إنشاء سند صرف", override_password_prompt)
    if amount_fils <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")

    voucher_no = settings_repo.reserve_next_number(conn, "voucher", "expense")
    return vouchers_repo.insert_expense(
        conn,
        voucher_no=voucher_no,
        description=description,
        amount_fils=amount_fils,
        expense_date=expense_date,
        note=note,
        created_by_user_id=user["id"],
    )


def create_purchase_invoice(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    supplier_name: str,
    purchase_date: str,
    items: list[dict],
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> int:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "إنشاء فاتورة شراء", override_password_prompt)
    if not supplier_name:
        raise ValueError("اسم المورد مطلوب")
    if not items:
        raise ValueError("يجب إضافة صنف واحد على الأقل")

    total_fils = sum_line_items_fils(items)
    voucher_no = settings_repo.reserve_next_number(conn, "voucher", "purchase")

    try:
        purchase_id = vouchers_repo.insert_purchase_invoice(
            conn,
            voucher_no=voucher_no,
            supplier_name=supplier_name,
            total_amount_fils=total_fils,
            purchase_date=purchase_date,
            note=note,
            created_by_user_id=user["id"],
        )
        for item in items:
            vouchers_repo.insert_purchase_invoice_item(
                conn,
                purchase_id,
                description=item["description"],
                quantity=item["quantity"],
                unit_price_fils=item["unit_price_fils"],
                line_total_fils=line_total_fils(item["quantity"], item["unit_price_fils"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return purchase_id
