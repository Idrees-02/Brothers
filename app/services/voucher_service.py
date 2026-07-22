"""Expense vouchers (سندات صرف), receipt vouchers (سندات قبض), and purchase
invoices (فواتير شراء)."""

import sqlite3

from app.domain.invoice_calc import line_total_fils, sum_line_items_fils
from app.domain.permissions import Permission
from app.domain.tax import compute_tax
from app.repositories import accounts_repo, settings_repo, vouchers_repo
from app.services.permission_service import OverridePrompt, require_permission


def _validate_account(conn: sqlite3.Connection, account_id: int) -> None:
    account = accounts_repo.get_account(conn, account_id)
    if account is None or not account["is_active"]:
        raise ValueError("الحساب المحدد غير صالح")


def create_expense(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    description: str,
    amount_fils: int,
    expense_date: str,
    account_id: int,
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> int:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "إنشاء سند صرف", override_password_prompt)
    if amount_fils <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
    _validate_account(conn, account_id)

    voucher_no = settings_repo.reserve_next_number(conn, "voucher", "expense")
    return vouchers_repo.insert_expense(
        conn,
        voucher_no=voucher_no,
        description=description,
        amount_fils=amount_fils,
        expense_date=expense_date,
        account_id=account_id,
        note=note,
        created_by_user_id=user["id"],
    )


def update_expense(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    expense_id: int,
    description: str,
    amount_fils: int,
    expense_date: str,
    account_id: int,
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> None:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "تعديل سند صرف", override_password_prompt)
    if amount_fils <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
    _validate_account(conn, account_id)

    try:
        vouchers_repo.update_expense(
            conn,
            expense_id,
            description=description,
            amount_fils=amount_fils,
            expense_date=expense_date,
            account_id=account_id,
            note=note,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def create_receipt(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    description: str,
    amount_fils: int,
    receipt_date: str,
    account_id: int,
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> int:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "إنشاء سند قبض", override_password_prompt)
    if amount_fils <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
    _validate_account(conn, account_id)

    voucher_no = settings_repo.reserve_next_number(conn, "voucher", "receipt")
    return vouchers_repo.insert_receipt(
        conn,
        voucher_no=voucher_no,
        description=description,
        amount_fils=amount_fils,
        receipt_date=receipt_date,
        account_id=account_id,
        note=note,
        created_by_user_id=user["id"],
    )


def update_receipt(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    receipt_id: int,
    description: str,
    amount_fils: int,
    receipt_date: str,
    account_id: int,
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> None:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "تعديل سند قبض", override_password_prompt)
    if amount_fils <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")
    _validate_account(conn, account_id)

    try:
        vouchers_repo.update_receipt(
            conn,
            receipt_id,
            description=description,
            amount_fils=amount_fils,
            receipt_date=receipt_date,
            account_id=account_id,
            note=note,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def create_purchase_invoice(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    supplier_name: str,
    purchase_date: str,
    items: list[dict],
    override_password_prompt: OverridePrompt,
    tax_included: bool = False,
    note: str | None = None,
    tax_rate_percent: float | None = None,
    account_id: int | None = None,
    is_credit: bool = False,
) -> int:
    """is_credit=True (فاتورة شراء آجلة) requires an account and keeps the
    purchase out of the financial report until settle_purchase_invoice marks
    it paid. tax_rate_percent=None snapshots the current Settings rate."""
    require_permission(conn, user, Permission.CREATE_VOUCHER, "إنشاء فاتورة شراء", override_password_prompt)
    if not supplier_name:
        raise ValueError("اسم المورد مطلوب")
    if not items:
        raise ValueError("يجب إضافة صنف واحد على الأقل")
    if is_credit and account_id is None:
        raise ValueError("يجب اختيار الحساب للفاتورة الآجلة")
    if account_id is not None:
        _validate_account(conn, account_id)

    settings = settings_repo.get_settings(conn)
    subtotal_fils = sum_line_items_fils(items)
    rate = settings["tax_rate_percent"] if tax_rate_percent is None else tax_rate_percent
    tax = compute_tax(subtotal_fils, rate, tax_included)
    voucher_no = settings_repo.reserve_next_number(conn, "voucher", "purchase")

    try:
        purchase_id = vouchers_repo.insert_purchase_invoice(
            conn,
            voucher_no=voucher_no,
            supplier_name=supplier_name,
            total_amount_fils=tax.grand_total_fils,
            subtotal_fils=tax.subtotal_fils,
            tax_included=int(tax_included),
            tax_rate_percent=tax.tax_rate_percent,
            tax_amount_fils=tax.tax_amount_fils,
            purchase_date=purchase_date,
            note=note,
            account_id=account_id,
            is_credit=int(is_credit),
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


def settle_purchase_invoice(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    purchase_invoice_id: int,
    override_password_prompt: OverridePrompt,
) -> None:
    """Marks a credit purchase invoice (فاتورة شراء آجلة) as paid - from
    this moment it starts counting in the financial report."""
    require_permission(conn, user, Permission.CREATE_VOUCHER, "تسديد فاتورة شراء آجلة", override_password_prompt)
    purchase = vouchers_repo.get_purchase_invoice(conn, purchase_invoice_id)
    if purchase is None:
        raise ValueError("فاتورة الشراء غير موجودة")
    header = purchase["header"]
    if not header["is_credit"]:
        raise ValueError("هذه الفاتورة نقدية وليست آجلة")
    if header["paid_at"] is not None:
        raise ValueError("تم تسديد هذه الفاتورة بالفعل")
    vouchers_repo.settle_purchase_invoice(conn, purchase_invoice_id)
