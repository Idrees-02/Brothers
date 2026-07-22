"""Installation / custom-fit invoice screen (فاتورة التركيب والتفصيل).
Supports browsing existing invoices (previous/next, or jump to an invoice
number - driven by the shared InvoicesScreen navigator, which also handles
switching to this tab when browsing lands on an installation-type invoice),
editing a previously saved one inline, and an unsaved-changes guard before
navigating away.

Editing an existing invoice only supports the same fields
invoice_service.update_invoice supports (customer info, tax, payment
method, line items) - deposit/installation-date/with-installation are
managed through dedicated flows elsewhere (recording a payment, the
installation schedule screen, etc.), so those fields are shown for context
but disabled while browsing."""

import sqlite3

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
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
from app.ui.widgets.card import Card, scrollable
from app.ui.widgets.compact_form import labeled_field as _labeled
from app.ui.widgets.dirty_tracker import DirtyTracker
from app.ui.widgets.line_items_table import LineItemsTable
from app.ui.widgets.money_spinbox import MoneySpinBox
from app.ui.widgets.override_dialog import prompt_override_password
from app.ui.widgets.payment_method_combo import PaymentMethodCombo


class InstallationInvoiceForm(QWidget):
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

        subtitle = QLabel("التسعير بالمتر المربع")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        form = QVBoxLayout()
        form.setSpacing(12)

        self.customer_name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.area_region_input = QLineEdit()
        identity_row = QHBoxLayout()
        identity_row.addLayout(_labeled("اسم الزبون *", self.customer_name_input))
        identity_row.addLayout(_labeled("رقم الهاتف *", self.phone_input))
        identity_row.addLayout(_labeled("المنطقة *", self.area_region_input))
        form.addLayout(identity_row)

        self.address_input = QLineEdit()
        form.addLayout(_labeled("العنوان (اختياري)", self.address_input))

        layout.addLayout(form)

        self.items_table = LineItemsTable(quantity_label="المتر المربع", conn=conn)
        self.items_table.set_tax_rate(settings_repo.get_settings(conn)["tax_rate_percent"])
        self.items_table.items_changed.connect(self._update_remaining_preview)
        layout.addWidget(self.items_table)

        # Deposit/installation/payment details all live in one compact row
        # below the items table (and its add/remove buttons).
        self.deposit_input = MoneySpinBox()
        self.deposit_input.setMaximumWidth(240)
        self.deposit_input.valueChanged.connect(self._update_remaining_preview)
        self.with_installation_checkbox = QCheckBox("مع التركيب (تُضاف رسوم التركيب)")
        self.with_installation_checkbox.stateChanged.connect(self._update_remaining_preview)
        self.installation_date_input = QDateEdit(QDate.currentDate())
        self.installation_date_input.setMaximumWidth(240)
        self.installation_date_input.setCalendarPopup(True)
        self.installation_date_input.setDisplayFormat("yyyy-MM-dd")
        self.payment_method_combo = PaymentMethodCombo()
        self.payment_method_combo.setMaximumWidth(240)
        self.tax_included_checkbox = QCheckBox("المبلغ شامل الضريبة")
        self.tax_included_checkbox.stateChanged.connect(self._on_tax_included_changed)
        details_row = QHBoxLayout()
        details_row.addLayout(_labeled("المقدم (يُدفع عند الحجز)", self.deposit_input))
        details_row.addWidget(self.with_installation_checkbox)
        details_row.addLayout(_labeled("تاريخ التركيب", self.installation_date_input))
        details_row.addLayout(_labeled("طريقة دفع المقدم *", self.payment_method_combo))
        details_row.addWidget(self.tax_included_checkbox)
        details_row.addStretch()
        layout.addLayout(details_row)

        self.remaining_preview_label = QLabel()
        self.remaining_preview_label.setObjectName("statValueNet")
        layout.addWidget(self.remaining_preview_label)
        self.items_table.add_row()
        self._update_remaining_preview()

        self._dirty_tracker = DirtyTracker(self)
        self._dirty_tracker.watch(
            self.customer_name_input,
            self.phone_input,
            self.area_region_input,
            self.address_input,
            self.with_installation_checkbox,
            self.deposit_input,
            self.installation_date_input,
            self.tax_included_checkbox,
            self.payment_method_combo,
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
            self.with_installation_checkbox.setChecked(bool(header["with_installation"]))
            self.deposit_input.set_fils_value(header["deposit_fils"])
            if header["installation_date"]:
                self.installation_date_input.setDate(
                    QDate.fromString(header["installation_date"], "yyyy-MM-dd")
                )
            self.tax_included_checkbox.setChecked(bool(header["tax_included"]))
            self.payment_method_combo.set_method(header["payment_method"])
            self.items_table.clear_rows()
            for item in invoice["items"]:
                self.items_table.add_row(
                    item["description"], item["quantity"], item["unit_price_fils"] / 1000
                )

        self._dirty_tracker.set_fields_silently(apply)
        # Deposit/installation-date/with-installation aren't editable through
        # this path (see module docstring) - shown for context, not blank.
        self.with_installation_checkbox.setEnabled(False)
        self.deposit_input.setEnabled(False)
        self.installation_date_input.setEnabled(False)

        self.save_button.setText("حفظ التعديلات")
        self.export_button.setEnabled(True)

    def start_new(self) -> None:
        if not self._dirty_tracker.confirm_discard():
            return
        self._browsed_id = None
        self.with_installation_checkbox.setEnabled(True)
        self.deposit_input.setEnabled(True)
        self.installation_date_input.setEnabled(True)
        self.save_button.setText("حفظ الفاتورة")
        self.export_button.setEnabled(self._last_invoice_id is not None)
        self._reset_form()
        self._dirty_tracker.mark_clean()

    # ------------------------------------------------------------ saving
    def _save(self) -> None:
        self._do_save(then_print=False)

    def _save_and_print(self) -> None:
        self._do_save(then_print=True)

    def _do_save(self, then_print: bool) -> None:
        items = self.items_table.items()
        try:
            if self._browsed_id is None:
                invoice_id = invoice_service.create_installation_invoice(
                    self._conn,
                    self._user,
                    customer_name=self.customer_name_input.text().strip(),
                    phone=self.phone_input.text().strip(),
                    area_region=self.area_region_input.text().strip(),
                    items=items,
                    with_installation=self.with_installation_checkbox.isChecked(),
                    deposit_fils=self.deposit_input.fils_value(),
                    # The table always yields ex-tax unit prices regardless
                    # of the entry-mode checkbox, so tax must be added on top.
                    tax_included=False,
                    payment_method=self.payment_method_combo.selected_method(),
                    override_password_prompt=lambda: prompt_override_password(
                        "إنشاء فاتورة تركيب وتفصيل", self
                    ),
                    address=self.address_input.text().strip() or None,
                    installation_date=self.installation_date_input.date().toString("yyyy-MM-dd"),
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
                    address=self.address_input.text().strip() or None,
                    area_region=self.area_region_input.text().strip() or None,
                    payment_method=self.payment_method_combo.selected_method(),
                )
                invoice_id = self._browsed_id
        except Exception as exc:  # noqa: BLE001 - surface any domain/service error to the user
            QMessageBox.warning(self, "تعذر حفظ الفاتورة", str(exc))
            return

        self._last_invoice_id = invoice_id
        self.export_button.setEnabled(True)
        header = invoices_repo.get_invoice(self._conn, invoice_id)["header"]
        status_label = "محجوزة (بانتظار المتبقي)" if header["status"] == "booked" else "مكتملة"
        QMessageBox.information(
            self, "تم الحفظ", f"تم إنشاء الفاتورة رقم {header['invoice_no']} - الحالة: {status_label}"
        )
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
        self.address_input.clear()
        self.area_region_input.clear()
        self.with_installation_checkbox.setChecked(False)
        self.deposit_input.setValue(0)
        self.tax_included_checkbox.setChecked(False)
        self.payment_method_combo.setCurrentIndex(0)
        self.installation_date_input.setDate(QDate.currentDate())
        self.items_table.clear_rows()
        self.items_table.add_row()
        self._update_remaining_preview()

    def _print_invoice(self, invoice_id: int) -> None:
        invoice = invoices_repo.get_invoice(self._conn, invoice_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        show_print_dialog(self, invoice, shop_name)

    def _on_tax_included_changed(self, *_args) -> None:
        self.items_table.set_tax_included(self.tax_included_checkbox.isChecked())
        self._update_remaining_preview()

    def _update_remaining_preview(self, *_args) -> None:
        settings = settings_repo.get_settings(self._conn)
        self.items_table.set_tax_rate(settings["tax_rate_percent"])
        items = self.items_table.items()
        subtotal_fils = sum_line_items_fils(items)
        if self.with_installation_checkbox.isChecked():
            subtotal_fils += settings["default_installation_fee_fils"]
        # The items table always yields ex-tax unit prices (even in
        # tax-included entry mode), so tax is always added on top here.
        tax = compute_tax(subtotal_fils, settings["tax_rate_percent"], False)
        deposit_fils = self.deposit_input.fils_value()
        remaining_fils = max(0, tax.grand_total_fils - min(deposit_fils, tax.grand_total_fils))
        self.remaining_preview_label.setText(
            f"الإجمالي: {fils_to_bhd_str(tax.grand_total_fils)} د.ب"
            f"  -  المتبقي بعد المقدم: {fils_to_bhd_str(remaining_fils)} د.ب"
        )

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
