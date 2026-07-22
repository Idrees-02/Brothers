"""Invoice creation/search/payment workflows for both invoice types."""

import sqlite3
from datetime import date

from app.domain.invoice_calc import (
    line_total_fils,
    remaining_balance_fils,
    sum_line_items_fils,
)
from app.domain.permissions import Permission
from app.domain.tax import compute_tax
from app.repositories import invoices_repo, settings_repo
from app.services import inventory_service
from app.services.permission_service import OverridePrompt, require_permission

CASH_PLACEHOLDER_NAME = "نقدي"

PAYMENT_METHODS = ("cash", "benefit_pay", "mastercard", "cheque")
PAYMENT_METHOD_LABELS_AR = {
    "cash": "نقداً",
    "benefit_pay": "بنفت باي",
    "mastercard": "ماستركارد",
    "cheque": "شيك",
}


def _validate_payment_method(payment_method: str) -> None:
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("طريقة الدفع مطلوبة")


def create_cash_invoice(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    phone: str,
    items: list[dict],
    tax_included: bool,
    payment_method: str,
    override_password_prompt: OverridePrompt,
    customer_name: str | None = None,
) -> int:
    require_permission(
        conn, user, Permission.CREATE_INVOICE, "إنشاء فاتورة قطع جاهزة", override_password_prompt
    )
    if not phone:
        raise ValueError("رقم الهاتف مطلوب")
    if not items:
        raise ValueError("يجب إضافة صنف واحد على الأقل")
    _validate_payment_method(payment_method)

    settings = settings_repo.get_settings(conn)
    subtotal_fils = sum_line_items_fils(items)
    tax = compute_tax(subtotal_fils, settings["tax_rate_percent"], tax_included)
    invoice_no = settings_repo.reserve_next_number(conn, "invoice", "cash")

    try:
        invoice_id = invoices_repo.insert_invoice(
            conn,
            invoice_type="cash",
            invoice_no=invoice_no,
            customer_name=customer_name or CASH_PLACEHOLDER_NAME,
            phone=phone,
            address=None,
            area_region=None,
            status="completed",
            with_installation=None,
            subtotal_fils=tax.subtotal_fils,
            tax_included=int(tax_included),
            tax_rate_percent=tax.tax_rate_percent,
            tax_amount_fils=tax.tax_amount_fils,
            grand_total_fils=tax.grand_total_fils,
            deposit_fils=0,
            payment_method=payment_method,
            created_by_user_id=user["id"],
        )
        for item in items:
            invoices_repo.insert_invoice_item(
                conn,
                invoice_id,
                description=item["description"],
                quantity=item["quantity"],
                unit=item.get("unit", "piece"),
                unit_price_fils=item["unit_price_fils"],
                line_total_fils=line_total_fils(item["quantity"], item["unit_price_fils"]),
            )
        invoices_repo.insert_invoice_payment(
            conn, invoice_id, "full", tax.grand_total_fils, user["id"]
        )
        inventory_service.decrement_stock_for_sale(
            conn, user, invoice_id, date.today().isoformat(), items
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return invoice_id


def create_installation_invoice(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    customer_name: str,
    phone: str,
    area_region: str,
    items: list[dict],
    with_installation: bool,
    deposit_fils: int,
    tax_included: bool,
    payment_method: str,
    override_password_prompt: OverridePrompt,
    address: str | None = None,
    installation_date: str | None = None,
) -> int:
    require_permission(
        conn, user, Permission.CREATE_INVOICE, "إنشاء فاتورة تركيب وتفصيل", override_password_prompt
    )
    if not customer_name:
        raise ValueError("اسم الزبون مطلوب")
    if not phone:
        raise ValueError("رقم الهاتف مطلوب")
    if not area_region:
        raise ValueError("المنطقة مطلوبة")
    if not items:
        raise ValueError("يجب إضافة صنف واحد على الأقل")
    _validate_payment_method(payment_method)

    settings = settings_repo.get_settings(conn)
    line_items = list(items)
    if with_installation:
        line_items.append(
            {
                "description": "رسوم التركيب",
                "quantity": 1,
                "unit": "piece",
                "unit_price_fils": settings["default_installation_fee_fils"],
            }
        )

    subtotal_fils = sum_line_items_fils(line_items)
    tax = compute_tax(subtotal_fils, settings["tax_rate_percent"], tax_included)
    remaining_balance_fils(tax.grand_total_fils, deposit_fils)  # raises if deposit invalid
    status = "completed" if deposit_fils >= tax.grand_total_fils else "booked"
    invoice_no = settings_repo.reserve_next_number(conn, "invoice", "installation")

    try:
        invoice_id = invoices_repo.insert_invoice(
            conn,
            invoice_type="installation",
            invoice_no=invoice_no,
            customer_name=customer_name,
            phone=phone,
            address=address,
            area_region=area_region,
            status=status,
            with_installation=int(with_installation),
            subtotal_fils=tax.subtotal_fils,
            tax_included=int(tax_included),
            tax_rate_percent=tax.tax_rate_percent,
            tax_amount_fils=tax.tax_amount_fils,
            grand_total_fils=tax.grand_total_fils,
            deposit_fils=deposit_fils,
            payment_method=payment_method,
            installation_date=installation_date,
            installation_status="pending",
            created_by_user_id=user["id"],
        )
        for item in line_items:
            invoices_repo.insert_invoice_item(
                conn,
                invoice_id,
                description=item["description"],
                quantity=item["quantity"],
                unit=item.get("unit", "piece"),
                unit_price_fils=item["unit_price_fils"],
                line_total_fils=line_total_fils(item["quantity"], item["unit_price_fils"]),
            )
        if deposit_fils > 0:
            payment_type = "full" if status == "completed" else "deposit"
            invoices_repo.insert_invoice_payment(conn, invoice_id, payment_type, deposit_fils, user["id"])
        inventory_service.decrement_stock_for_sale(
            conn, user, invoice_id, date.today().isoformat(), items
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return invoice_id


def update_invoice(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    invoice_id: int,
    phone: str,
    items: list[dict],
    tax_included: bool,
    override_password_prompt: OverridePrompt,
    customer_name: str | None = None,
    address: str | None = None,
    area_region: str | None = None,
    payment_method: str | None = None,
) -> dict:
    """Edits an existing invoice's customer info and line items. The tax
    rate stays whatever was snapshotted at creation time - editing never
    changes which rate applied. Deposits/payments already recorded are left
    untouched, but the new total can never drop below what's already paid.
    """
    require_permission(conn, user, Permission.EDIT_INVOICE, "تعديل فاتورة", override_password_prompt)
    invoice = invoices_repo.get_invoice(conn, invoice_id)
    if invoice is None:
        raise ValueError("الفاتورة غير موجودة")
    header = invoice["header"]
    if not phone:
        raise ValueError("رقم الهاتف مطلوب")
    if header["invoice_type"] == "installation":
        if not customer_name:
            raise ValueError("اسم الزبون مطلوب")
        if not area_region:
            raise ValueError("المنطقة مطلوبة")
    if not items:
        raise ValueError("يجب إضافة صنف واحد على الأقل")
    if payment_method is not None:
        _validate_payment_method(payment_method)

    subtotal_fils = sum_line_items_fils(items)
    tax = compute_tax(subtotal_fils, header["tax_rate_percent"], tax_included)

    paid_so_far = sum(p["amount_fils"] for p in invoice["payments"])
    if tax.grand_total_fils < paid_so_far:
        raise ValueError("لا يمكن تخفيض إجمالي الفاتورة إلى أقل من المبلغ المدفوع بالفعل")

    try:
        invoices_repo.update_invoice_header(
            conn,
            invoice_id,
            customer_name=customer_name or (CASH_PLACEHOLDER_NAME if header["invoice_type"] == "cash" else None),
            phone=phone,
            address=address,
            area_region=area_region,
            subtotal_fils=tax.subtotal_fils,
            tax_included=int(tax_included),
            tax_amount_fils=tax.tax_amount_fils,
            grand_total_fils=tax.grand_total_fils,
            payment_method=payment_method or header["payment_method"],
        )
        invoices_repo.delete_invoice_items(conn, invoice_id)
        for item in items:
            invoices_repo.insert_invoice_item(
                conn,
                invoice_id,
                description=item["description"],
                quantity=item["quantity"],
                unit=item.get("unit", "piece"),
                unit_price_fils=item["unit_price_fils"],
                line_total_fils=line_total_fils(item["quantity"], item["unit_price_fils"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return invoices_repo.get_invoice(conn, invoice_id)


def record_remaining_payment(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    invoice_id: int,
    override_password_prompt: OverridePrompt,
    amount_fils: int | None = None,
) -> dict:
    require_permission(
        conn, user, Permission.EDIT_INVOICE, "تحصيل المبلغ المتبقي", override_password_prompt
    )
    invoice = invoices_repo.get_invoice(conn, invoice_id)
    if invoice is None:
        raise ValueError("الفاتورة غير موجودة")
    header = invoice["header"]
    paid_so_far = sum(p["amount_fils"] for p in invoice["payments"])
    remaining = remaining_balance_fils(header["grand_total_fils"], paid_so_far)
    if remaining <= 0:
        raise ValueError("تم سداد الفاتورة بالكامل")

    pay_amount = remaining if amount_fils is None else amount_fils
    if pay_amount > remaining:
        raise ValueError("المبلغ المدخل أكبر من المبلغ المتبقي")

    try:
        invoices_repo.insert_invoice_payment(conn, invoice_id, "remaining", pay_amount, user["id"])
        if pay_amount == remaining:
            invoices_repo.set_invoice_status(conn, invoice_id, "completed")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return invoices_repo.get_invoice(conn, invoice_id)


def void_invoice(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    invoice_id: int,
    override_password_prompt: OverridePrompt,
) -> None:
    require_permission(conn, user, Permission.EDIT_INVOICE, "إلغاء فاتورة", override_password_prompt)
    try:
        invoices_repo.void_invoice(conn, invoice_id, user["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def search_invoices(conn: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    return invoices_repo.search_invoices(conn, query)


def list_all_invoices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return invoices_repo.list_all_invoices(conn)


def list_installations_for_date(conn: sqlite3.Connection, work_date: str) -> list[sqlite3.Row]:
    return invoices_repo.list_installations_for_date(conn, work_date)


def assign_installer(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    invoice_id: int,
    employee_id: int | None,
    override_password_prompt: OverridePrompt,
) -> None:
    require_permission(
        conn, user, Permission.EDIT_INVOICE, "تعيين فني التركيب", override_password_prompt
    )
    invoices_repo.assign_installer(conn, invoice_id, employee_id)


def mark_installed(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    invoice_id: int,
    override_password_prompt: OverridePrompt,
) -> None:
    require_permission(conn, user, Permission.EDIT_INVOICE, "تأكيد تم التركيب", override_password_prompt)
    invoices_repo.set_installation_status(conn, invoice_id, "installed")


def postpone_installation(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    invoice_id: int,
    override_password_prompt: OverridePrompt,
    new_installation_date: str | None = None,
) -> None:
    """new_installation_date=None postpones indefinitely (clears the date so
    it drops out of every day's schedule); a date reschedules it directly."""
    require_permission(conn, user, Permission.EDIT_INVOICE, "تأجيل التركيب", override_password_prompt)
    if new_installation_date:
        invoices_repo.set_installation_status(
            conn, invoice_id, "pending", installation_date=new_installation_date
        )
    else:
        invoices_repo.clear_installation_date(conn, invoice_id)


def cancel_installation(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    invoice_id: int,
    override_password_prompt: OverridePrompt,
) -> None:
    require_permission(conn, user, Permission.EDIT_INVOICE, "إلغاء التركيب", override_password_prompt)
    invoices_repo.set_installation_status(conn, invoice_id, "cancelled")
