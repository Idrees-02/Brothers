"""Cash / ready-made invoice screen (فاتورة قطع جاهزة). Supports browsing
existing invoices (previous/next, or jump to an invoice number - driven by
the shared InvoicesScreen navigator, which also handles switching to this
tab when browsing lands on a cash-type invoice), editing a previously saved
one inline, and an unsaved-changes guard before navigating away.

Also supports an optional delivery leg ("مع التوصيل"): when checked, the
invoice goes through the exact same installation-schedule/outcome workflow
as an installation invoice (see invoices_repo.list_installations_for_date),
and a "رسوم التوصيل" line item is added to the table automatically (at the
default fee from Settings, freely editable/removable). Editing an existing
invoice only supports the same fields invoice_service.update_invoice
supports (customer info, tax, payment method, line items) - delivery
region/address/deposit/date are managed through dedicated flows elsewhere
(the installation schedule screen), so those fields are shown for context
but disabled while browsing, matching InstallationInvoiceForm."""

import sqlite3

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.domain.invoice_calc import sum_line_items_fils
from app.domain.money import fils_to_bhd_str
from app.domain.tax import compute_tax
from app.repositories import invoices_repo, settings_repo
from app.services import invoice_service
from app.ui.invoices.invoice_print import export_invoice_pdf, show_print_dialog
from app.ui.widgets.account_combo import AccountCombo
from app.ui.widgets.card import Card, scrollable
from app.ui.widgets.compact_form import expand_width as _expand
from app.ui.widgets.compact_form import labeled_field as _labeled
from app.ui.widgets.dirty_tracker import DirtyTracker
from app.ui.widgets.line_items_table import LineItemsTable
from app.ui.widgets.money_spinbox import MoneySpinBox
from app.ui.widgets.override_dialog import prompt_override_password
from app.ui.widgets.payment_method_combo import PaymentMethodCombo

_DELIVERY_FEE_DESCRIPTION = "رسوم التوصيل"


class CashInvoiceForm(QWidget):
    invoice_saved = Signal(int)  # emits the created/updated invoice's id

    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._browsed_id: int | None = None  # None = "new invoice" mode
        self._last_invoice_id: int | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(scrollable(card))
        layout = card.body_layout

        subtitle = QLabel("المبلغ يُدفع بالكامل عند الاستلام - أو عند التوصيل إن وُجد")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        form = QVBoxLayout()
        form.setSpacing(12)

        # Row 1: customer identity/classification, spread edge-to-edge.
        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText("اختياري - يُملأ تلقائياً بـ \"نقدي\"")
        self.account_combo = AccountCombo(conn, allow_empty=True)
        _expand(self.account_combo)
        self.invoice_kind_combo = QComboBox()
        self.invoice_kind_combo.addItem("نقدا", False)
        self.invoice_kind_combo.addItem("آجل", True)
        _expand(self.invoice_kind_combo)
        identity_row = QHBoxLayout()
        identity_row.addLayout(_labeled("اسم الزبون", self.customer_name_input), 1)
        identity_row.addLayout(_labeled("الحساب", self.account_combo), 1)
        identity_row.addLayout(_labeled("نوع الفاتورة", self.invoice_kind_combo), 1)
        form.addLayout(identity_row)

        # Row 2: contact details, spread edge-to-edge.
        self.phone_input = QLineEdit()
        self.address_input = QLineEdit()
        self.area_region_input = QLineEdit()
        contact_row = QHBoxLayout()
        contact_row.addLayout(_labeled("رقم الهاتف *", self.phone_input), 1)
        contact_row.addLayout(_labeled("العنوان (للتوصيل)", self.address_input), 1)
        contact_row.addLayout(_labeled("المنطقة (للتوصيل)", self.area_region_input), 1)
        form.addLayout(contact_row)

        # Row 3: delivery/tax toggles, spread edge-to-edge.
        self.with_delivery_checkbox = QCheckBox("مع التوصيل")
        self.with_delivery_checkbox.toggled.connect(self._on_delivery_toggled)
        self.tax_included_checkbox = QCheckBox("المبلغ شامل الضريبة")
        self.tax_included_checkbox.stateChanged.connect(self._on_tax_included_changed)
        self.tax_rate_input = QDoubleSpinBox()
        self.tax_rate_input.setDecimals(2)
        self.tax_rate_input.setRange(0.0, 100.0)
        self.tax_rate_input.setSuffix(" %")
        _expand(self.tax_rate_input)
        self.tax_rate_input.setValue(settings_repo.get_settings(conn)["tax_rate_percent"])
        self.tax_rate_input.valueChanged.connect(self._update_remaining_preview)
        toggles_row = QHBoxLayout()
        toggles_row.addWidget(self.with_delivery_checkbox, 1)
        toggles_row.addWidget(self.tax_included_checkbox, 1)
        toggles_row.addLayout(_labeled("نسبة الضريبة", self.tax_rate_input), 1)
        form.addLayout(toggles_row)

        layout.addLayout(form)

        self.items_table = LineItemsTable(quantity_label="الكمية", conn=conn)
        self.items_table.set_tax_rate(settings_repo.get_settings(conn)["tax_rate_percent"])
        self.items_table.items_changed.connect(self._update_remaining_preview)
        layout.addWidget(self.items_table)

        # Last row: discount, deposit, payment method, and the
        # delivery/installation date - spread edge-to-edge below the items
        # table (and its add/remove buttons).
        self.discount_input = MoneySpinBox()
        _expand(self.discount_input)
        self.discount_input.valueChanged.connect(self._update_remaining_preview)
        self.deposit_input = MoneySpinBox()
        _expand(self.deposit_input)
        self.deposit_input.valueChanged.connect(self._update_remaining_preview)
        self.payment_method_combo = PaymentMethodCombo()
        _expand(self.payment_method_combo)
        self.delivery_date_input = QDateEdit(QDate.currentDate())
        _expand(self.delivery_date_input)
        self.delivery_date_input.setCalendarPopup(True)
        self.delivery_date_input.setDisplayFormat("yyyy-MM-dd")
        self.delivery_date_input.setEnabled(False)
        billing_row = QHBoxLayout()
        billing_row.addLayout(_labeled("التخفيض", self.discount_input), 1)
        billing_row.addLayout(_labeled("المقدم (المبلغ المدفوع)", self.deposit_input), 1)
        billing_row.addLayout(_labeled("طريقة الدفع *", self.payment_method_combo), 1)
        billing_row.addLayout(_labeled("تاريخ التوصيل", self.delivery_date_input), 1)
        layout.addLayout(billing_row)

        self.remaining_preview_label = QLabel()
        self.remaining_preview_label.setObjectName("statValueNet")
        layout.addWidget(self.remaining_preview_label)
        self.tax_included_checkbox.setChecked(True)  # default: totals entered tax-inclusive
        self.items_table.add_row()
        self._update_remaining_preview()

        self._dirty_tracker = DirtyTracker(self)
        self._dirty_tracker.watch(
            self.customer_name_input,
            self.phone_input,
            self.area_region_input,
            self.address_input,
            self.with_delivery_checkbox,
            self.deposit_input,
            self.delivery_date_input,
            self.tax_included_checkbox,
            self.payment_method_combo,
            self.discount_input,
            self.tax_rate_input,
            self.invoice_kind_combo,
            self.account_combo,
            self.items_table,
        )

        buttons_row = QHBoxLayout()
        self.save_button = QPushButton("حفظ الفاتورة")
        self.save_button.clicked.connect(self._save)
        buttons_row.addWidget(self.save_button)

        self.save_print_button = QPushButton("طباعة وحفظ الفاتورة")
        self.save_print_button.clicked.connect(self._save_and_print)
        buttons_row.addWidget(self.save_print_button)

        self.export_button = QPushButton("تصدير PDF")
        self.export_button.clicked.connect(self._export)
        self.export_button.setEnabled(False)
        buttons_row.addWidget(self.export_button)

        buttons_row.addStretch()
        layout.addLayout(buttons_row)
        layout.addStretch()

    # ------------------------------------------------------- public API
    # (used by InvoicesScreen, which owns the shared prev/next/search bar
    # across both invoice-type tabs)
    def is_dirty(self) -> bool:
        return self._dirty_tracker.is_dirty()

    def confirm_discard(self) -> bool:
        return self._dirty_tracker.confirm_discard()

    def load_invoice_for_edit(self, invoice_id: int) -> None:
        invoice = invoices_repo.get_invoice(self._conn, invoice_id)
        header = invoice["header"]
        self._browsed_id = invoice_id

        def apply():
            self.customer_name_input.setText(header["customer_name"] or "")
            self.phone_input.setText(header["phone"])
            self.area_region_input.setText(header["area_region"] or "")
            self.address_input.setText(header["address"] or "")
            self.with_delivery_checkbox.setChecked(bool(header["with_delivery"]))
            self.deposit_input.set_fils_value(header["deposit_fils"])
            if header["installation_date"]:
                self.delivery_date_input.setDate(
                    QDate.fromString(header["installation_date"], "yyyy-MM-dd")
                )
            self.tax_included_checkbox.setChecked(bool(header["tax_included"]))
            self.payment_method_combo.set_method(header["payment_method"])
            self.discount_input.set_fils_value(header["discount_fils"])
            self.tax_rate_input.setValue(header["tax_rate_percent"])
            self.invoice_kind_combo.setCurrentIndex(1 if header["is_credit"] else 0)
            self.account_combo.set_account(header["account_id"])
            self.items_table.set_tax_rate(header["tax_rate_percent"])
            self.items_table.clear_rows()
            for item in invoice["items"]:
                self.items_table.add_row(
                    item["description"], item["quantity"], item["unit_price_fils"] / 1000
                )

        self._dirty_tracker.set_fields_silently(apply)
        # Delivery fields aren't editable through this path (see module
        # docstring) - shown for context, not blank.
        self.area_region_input.setEnabled(False)
        self.address_input.setEnabled(False)
        self.with_delivery_checkbox.setEnabled(False)
        self.deposit_input.setEnabled(False)
        self.delivery_date_input.setEnabled(False)

        self.save_button.setText("حفظ التعديلات")
        self.export_button.setEnabled(True)

    def start_new(self) -> None:
        if not self._dirty_tracker.confirm_discard():
            return
        self._browsed_id = None
        self.area_region_input.setEnabled(True)
        self.address_input.setEnabled(True)
        self.with_delivery_checkbox.setEnabled(True)
        self.deposit_input.setEnabled(True)
        self.save_button.setText("حفظ الفاتورة")
        self.export_button.setEnabled(self._last_invoice_id is not None)
        self._reset_form()
        self._dirty_tracker.mark_clean()

    # --------------------------------------------------------------- tax
    def _on_tax_included_changed(self, *_args) -> None:
        self.items_table.set_tax_included(self.tax_included_checkbox.isChecked())
        self._update_remaining_preview()

    def _update_remaining_preview(self, *_args) -> None:
        rate = self.tax_rate_input.value()
        self.items_table.set_tax_rate(rate)
        subtotal_fils = sum_line_items_fils(self.items_table.items())
        discount_fils = min(self.discount_input.fils_value(), subtotal_fils)
        # The items table always yields ex-tax unit prices (even in
        # tax-included entry mode), so tax is always added on top here.
        tax = compute_tax(subtotal_fils - discount_fils, rate, False)
        deposit_fils = self.deposit_input.fils_value()
        remaining_fils = max(0, tax.grand_total_fils - min(deposit_fils, tax.grand_total_fils))
        self.remaining_preview_label.setText(
            f"الإجمالي: {fils_to_bhd_str(tax.grand_total_fils)} د.ب"
            f"  -  المتبقي بعد المقدم: {fils_to_bhd_str(remaining_fils)} د.ب"
        )

    # ---------------------------------------------------------- delivery
    def _on_delivery_toggled(self, checked: bool) -> None:
        # The deposit stays enabled either way - a partial payment can be
        # recorded on any invoice, delivery or not.
        self.delivery_date_input.setEnabled(checked)
        if checked:
            if not self.items_table.has_row_with_description(_DELIVERY_FEE_DESCRIPTION):
                fee_bhd = settings_repo.get_settings(self._conn)["default_delivery_fee_fils"] / 1000
                self.items_table.add_row(_DELIVERY_FEE_DESCRIPTION, 1, fee_bhd)
        else:
            self.items_table.remove_row_by_description(_DELIVERY_FEE_DESCRIPTION)

    # ------------------------------------------------------------ saving
    def _save(self) -> None:
        self._do_save(then_print=False)

    def _save_and_print(self) -> None:
        self._do_save(then_print=True)

    def _do_save(self, then_print: bool) -> None:
        items = self.items_table.items()
        with_delivery = self.with_delivery_checkbox.isChecked()
        if with_delivery and not self.area_region_input.text().strip():
            QMessageBox.warning(self, "تعذر حفظ الفاتورة", "المنطقة مطلوبة للتوصيل")
            return
        try:
            if self._browsed_id is None:
                invoice_id = invoice_service.create_cash_invoice(
                    self._conn,
                    self._user,
                    phone=self.phone_input.text().strip(),
                    items=items,
                    # The table always yields ex-tax unit prices regardless
                    # of the entry-mode checkbox, so tax must be added on top.
                    tax_included=False,
                    payment_method=self.payment_method_combo.selected_method(),
                    override_password_prompt=lambda: prompt_override_password(
                        "إنشاء فاتورة قطع جاهزة", self
                    ),
                    customer_name=self.customer_name_input.text().strip() or None,
                    with_delivery=with_delivery,
                    area_region=self.area_region_input.text().strip() or None,
                    address=self.address_input.text().strip() or None,
                    deposit_fils=self.deposit_input.fils_value(),
                    delivery_date=(
                        self.delivery_date_input.date().toString("yyyy-MM-dd")
                        if with_delivery
                        else None
                    ),
                    discount_fils=self.discount_input.fils_value(),
                    tax_rate_percent=self.tax_rate_input.value(),
                    account_id=self.account_combo.selected_account_id(),
                    is_credit=bool(self.invoice_kind_combo.currentData()),
                )
            else:
                invoice_service.update_invoice(
                    self._conn,
                    self._user,
                    self._browsed_id,
                    phone=self.phone_input.text().strip(),
                    items=items,
                    tax_included=False,
                    override_password_prompt=lambda: prompt_override_password("تعديل فاتورة", self),
                    customer_name=self.customer_name_input.text().strip() or None,
                    payment_method=self.payment_method_combo.selected_method(),
                    discount_fils=self.discount_input.fils_value(),
                    tax_rate_percent=self.tax_rate_input.value(),
                    account_id=self.account_combo.selected_account_id(),
                    is_credit=bool(self.invoice_kind_combo.currentData()),
                )
                invoice_id = self._browsed_id
        except Exception as exc:  # noqa: BLE001 - surface any domain/service error to the user
            QMessageBox.warning(self, "تعذر حفظ الفاتورة", str(exc))
            return

        self._last_invoice_id = invoice_id
        self.export_button.setEnabled(True)
        invoice_no = invoices_repo.get_invoice(self._conn, invoice_id)["header"]["invoice_no"]
        QMessageBox.information(self, "تم الحفظ", f"تم إنشاء الفاتورة رقم {invoice_no}")
        if then_print:
            self._print_invoice(invoice_id)

        if self._browsed_id is None:
            self._reset_form()
            self._dirty_tracker.mark_clean()
        else:
            self.load_invoice_for_edit(invoice_id)
        self.invoice_saved.emit(invoice_id)

    def _reset_form(self) -> None:
        self.customer_name_input.clear()
        self.phone_input.clear()
        self.area_region_input.clear()
        self.address_input.clear()
        self.with_delivery_checkbox.setChecked(False)
        self.deposit_input.setValue(0)
        self.delivery_date_input.setDate(QDate.currentDate())
        self.tax_included_checkbox.setChecked(True)
        self.payment_method_combo.setCurrentIndex(0)
        self.discount_input.setValue(0)
        self.tax_rate_input.setValue(settings_repo.get_settings(self._conn)["tax_rate_percent"])
        self.invoice_kind_combo.setCurrentIndex(0)
        self.account_combo.refresh()
        self.account_combo.setCurrentIndex(0)
        self.items_table.clear_rows()
        self.items_table.add_row()
        self._update_remaining_preview()

    def _print_invoice(self, invoice_id: int) -> None:
        invoice = invoices_repo.get_invoice(self._conn, invoice_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        show_print_dialog(self, invoice, shop_name)

    def _export(self) -> None:
        target_id = self._browsed_id or self._last_invoice_id
        if target_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "تصدير PDF", "invoice.pdf", "PDF (*.pdf)")
        if not path:
            return
        invoice = invoices_repo.get_invoice(self._conn, target_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        export_invoice_pdf(invoice, shop_name, path)
