"""Cash / ready-made invoice screen (فاتورة قطع جاهزة). Supports browsing
existing invoices (previous/next, or jump to an invoice number - driven by
the shared InvoicesScreen navigator, which also handles switching to this
tab when browsing lands on a cash-type invoice), editing a previously saved
one inline, and an unsaved-changes guard before navigating away."""

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.repositories import invoices_repo, settings_repo
from app.services import invoice_service
from app.ui.invoices.invoice_print import export_invoice_pdf
from app.ui.widgets.card import Card, scrollable
from app.ui.widgets.dirty_tracker import DirtyTracker
from app.ui.widgets.line_items_table import LineItemsTable
from app.ui.widgets.override_dialog import prompt_override_password
from app.ui.widgets.payment_method_combo import PaymentMethodCombo


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

        subtitle = QLabel("المبلغ يُدفع بالكامل عند الاستلام")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText("اختياري - يُملأ تلقائياً بـ \"نقدي\"")
        form.addRow("اسم الزبون", self.customer_name_input)

        self.phone_input = QLineEdit()
        form.addRow("رقم الهاتف *", self.phone_input)

        self.tax_included_checkbox = QCheckBox("المبلغ شامل الضريبة")
        form.addRow(self.tax_included_checkbox)

        self.payment_method_combo = PaymentMethodCombo()
        form.addRow("طريقة الدفع *", self.payment_method_combo)
        layout.addLayout(form)

        self.items_table = LineItemsTable(quantity_label="الكمية", conn=conn)
        layout.addWidget(self.items_table)

        self._dirty_tracker = DirtyTracker(self)
        self._dirty_tracker.watch(
            self.customer_name_input,
            self.phone_input,
            self.tax_included_checkbox,
            self.payment_method_combo,
            self.items_table,
        )

        buttons_row = QHBoxLayout()
        self.save_button = QPushButton("حفظ الفاتورة")
        self.save_button.clicked.connect(self._save)
        buttons_row.addWidget(self.save_button)

        self.new_invoice_button = QPushButton("فاتورة جديدة")
        self.new_invoice_button.setObjectName("secondaryButton")
        self.new_invoice_button.clicked.connect(self.start_new)
        self.new_invoice_button.setEnabled(False)
        buttons_row.addWidget(self.new_invoice_button)

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
            self.tax_included_checkbox.setChecked(bool(header["tax_included"]))
            self.payment_method_combo.set_method(header["payment_method"])
            self.items_table.clear_rows()
            for item in invoice["items"]:
                self.items_table.add_row(
                    item["description"], item["quantity"], item["unit_price_fils"] / 1000
                )

        self._dirty_tracker.set_fields_silently(apply)
        self.save_button.setText("حفظ التعديلات")
        self.new_invoice_button.setEnabled(True)
        self.export_button.setEnabled(True)

    def start_new(self) -> None:
        if not self._dirty_tracker.confirm_discard():
            return
        self._browsed_id = None
        self.save_button.setText("حفظ الفاتورة")
        self.new_invoice_button.setEnabled(False)
        self.export_button.setEnabled(self._last_invoice_id is not None)
        self._reset_form()
        self._dirty_tracker.mark_clean()

    # ------------------------------------------------------------ saving
    def _save(self) -> None:
        items = self.items_table.items()
        try:
            if self._browsed_id is None:
                invoice_id = invoice_service.create_cash_invoice(
                    self._conn,
                    self._user,
                    phone=self.phone_input.text().strip(),
                    items=items,
                    tax_included=self.tax_included_checkbox.isChecked(),
                    payment_method=self.payment_method_combo.selected_method(),
                    override_password_prompt=lambda: prompt_override_password(
                        "إنشاء فاتورة قطع جاهزة", self
                    ),
                    customer_name=self.customer_name_input.text().strip() or None,
                )
            else:
                invoice_service.update_invoice(
                    self._conn,
                    self._user,
                    self._browsed_id,
                    phone=self.phone_input.text().strip(),
                    items=items,
                    tax_included=self.tax_included_checkbox.isChecked(),
                    override_password_prompt=lambda: prompt_override_password("تعديل فاتورة", self),
                    customer_name=self.customer_name_input.text().strip() or None,
                    payment_method=self.payment_method_combo.selected_method(),
                )
                invoice_id = self._browsed_id
        except Exception as exc:  # noqa: BLE001 - surface any domain/service error to the user
            QMessageBox.warning(self, "تعذر حفظ الفاتورة", str(exc))
            return

        self._last_invoice_id = invoice_id
        self.export_button.setEnabled(True)
        invoice_no = invoices_repo.get_invoice(self._conn, invoice_id)["header"]["invoice_no"]
        QMessageBox.information(self, "تم الحفظ", f"تم إنشاء الفاتورة رقم {invoice_no}")

        if self._browsed_id is None:
            self._reset_form()
            self._dirty_tracker.mark_clean()
        else:
            self.load_invoice_for_edit(invoice_id)
        self.invoice_saved.emit(invoice_id)

    def _reset_form(self) -> None:
        self.customer_name_input.clear()
        self.phone_input.clear()
        self.tax_included_checkbox.setChecked(False)
        self.payment_method_combo.setCurrentIndex(0)
        self.items_table.clear_rows()

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
