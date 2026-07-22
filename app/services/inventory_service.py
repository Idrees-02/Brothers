"""Inventory (المخزون): item CRUD, manual stock-in/out vouchers, and the
automatic stock decrement triggered by selling an inventory-linked item on a
cash/installation invoice."""

import sqlite3

from app.domain.permissions import Permission
from app.repositories import items_repo, settings_repo, stock_repo
from app.services.permission_service import OverridePrompt, require_permission

STOCK_OUT_REASONS = ("تالف", "إرجاع للمورد", "تسوية جرد", "استخدام داخلي", "أخرى")


def create_item(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    name: str,
    unit: str,
    unit_price_fils: int,
    override_password_prompt: OverridePrompt,
) -> int:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "إضافة صنف للمخزون", override_password_prompt)
    if not name:
        raise ValueError("اسم الصنف مطلوب")
    if items_repo.find_item_by_name(conn, name) is not None:
        raise ValueError("يوجد صنف بنفس الاسم بالفعل")
    return items_repo.create_item(conn, name=name, unit=unit, unit_price_fils=unit_price_fils)


def record_stock_in(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    item_id: int,
    quantity: float,
    movement_date: str,
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> int:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "إنشاء سند إدخال", override_password_prompt)
    if quantity <= 0:
        raise ValueError("الكمية يجب أن تكون أكبر من صفر")
    item = items_repo.get_item(conn, item_id)
    if item is None or not item["is_active"]:
        raise ValueError("الصنف المحدد غير صالح")

    voucher_no = settings_repo.reserve_next_number(conn, "voucher", "stock_in")
    try:
        movement_id = stock_repo.insert_stock_movement(
            conn,
            voucher_no=voucher_no,
            movement_type="in",
            item_id=item_id,
            quantity=quantity,
            reason=None,
            note=note,
            movement_date=movement_date,
            source="manual",
            created_by_user_id=user["id"],
        )
        items_repo.adjust_quantity(conn, item_id, quantity)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return movement_id


def record_stock_out(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    item_id: int,
    quantity: float,
    reason: str,
    movement_date: str,
    override_password_prompt: OverridePrompt,
    note: str | None = None,
) -> int:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "إنشاء سند إخراج", override_password_prompt)
    if quantity <= 0:
        raise ValueError("الكمية يجب أن تكون أكبر من صفر")
    if not reason:
        raise ValueError("سبب الإخراج مطلوب")
    item = items_repo.get_item(conn, item_id)
    if item is None or not item["is_active"]:
        raise ValueError("الصنف المحدد غير صالح")
    if item["quantity_on_hand"] < quantity:
        raise ValueError("الكمية المطلوب إخراجها أكبر من الكمية الموجودة في المخزون")

    voucher_no = settings_repo.reserve_next_number(conn, "voucher", "stock_out")
    try:
        movement_id = stock_repo.insert_stock_movement(
            conn,
            voucher_no=voucher_no,
            movement_type="out",
            item_id=item_id,
            quantity=quantity,
            reason=reason,
            note=note,
            movement_date=movement_date,
            source="manual",
            created_by_user_id=user["id"],
        )
        items_repo.adjust_quantity(conn, item_id, -quantity)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return movement_id


def decrement_stock_for_sale(
    conn: sqlite3.Connection, user: sqlite3.Row, invoice_id: int, invoice_date: str, items: list[dict]
) -> None:
    """Called from invoice_service right before its own commit. Line items
    typed freehand (no matching inventory item by name) are skipped silently
    - linking an invoice line to inventory is optional, not mandatory. Does
    not commit itself - part of the caller's transaction."""
    for line in items:
        item = items_repo.find_item_by_name(conn, line["description"])
        if item is None or not item["is_active"]:
            continue
        voucher_no = settings_repo.reserve_next_number(conn, "voucher", "stock_out")
        stock_repo.insert_stock_movement(
            conn,
            voucher_no=voucher_no,
            movement_type="out",
            item_id=item["id"],
            quantity=line["quantity"],
            reason=None,
            note=None,
            movement_date=invoice_date,
            source="sale",
            reference_invoice_id=invoice_id,
            created_by_user_id=user["id"],
        )
        items_repo.adjust_quantity(conn, item["id"], -line["quantity"])


def update_movement_note(
    conn: sqlite3.Connection,
    user: sqlite3.Row,
    movement_id: int,
    override_password_prompt: OverridePrompt,
    note: str | None,
    reason: str | None = None,
) -> None:
    require_permission(conn, user, Permission.CREATE_VOUCHER, "تعديل سند مخزون", override_password_prompt)
    try:
        stock_repo.update_movement_note(conn, movement_id, note=note, reason=reason)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
