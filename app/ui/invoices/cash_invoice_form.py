"""Cash / ready-made invoice screen (فاتورة قطع جاهزة)."""

import sqlite3

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
from app.ui.invoices.invoice_print import export_invoice_pdf, show_print_dialog
from app.ui.widgets.line_items_table import LineItemsTable
from app.ui.widgets.override_dialog import prompt_override_password


class CashInvoiceForm(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._last_invoice_id: int | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("فاتورة قطع جاهزة (المبلغ يُدفع بالكامل عند الاستلام)"))

        form = QFormLayout()
        self.customer_name_input = QLineEdit()
        self.customer_name_input.setPlaceholderText("اختياري - يُملأ تلقائياً بـ \"نقدي\"")
        form.addRow("اسم الزبون", self.customer_name_input)

        self.phone_input = QLineEdit()
        form.addRow("رقم الهاتف *", self.phone_input)

        self.tax_included_checkbox = QCheckBox("المبلغ شامل الضريبة")
        form.addRow(self.tax_included_checkbox)
        layout.addLayout(form)

        self.items_table = LineItemsTable(quantity_label="الكمية")
        layout.addWidget(self.items_table)

        buttons_row = QHBoxLayout()
        save_button = QPushButton("حفظ الفاتورة")
        save_button.clicked.connect(self._save)
        buttons_row.addWidget(save_button)

        self.print_button = QPushButton("طباعة آخر فاتورة")
        self.print_button.clicked.connect(self._print_last)
        self.print_button.setEnabled(False)
        buttons_row.addWidget(self.print_button)

        self.export_button = QPushButton("تصدير PDF")
        self.export_button.clicked.connect(self._export_last)
        self.export_button.setEnabled(False)
        buttons_row.addWidget(self.export_button)

        buttons_row.addStretch()
        layout.addLayout(buttons_row)
        layout.addStretch()

    def _save(self) -> None:
        items = self.items_table.items()
        try:
            invoice_id = invoice_service.create_cash_invoice(
                self._conn,
                self._user,
                phone=self.phone_input.text().strip(),
                items=items,
                tax_included=self.tax_included_checkbox.isChecked(),
                override_password_prompt=lambda: prompt_override_password(
                    "إنشاء فاتورة قطع جاهزة", self
                ),
                customer_name=self.customer_name_input.text().strip() or None,
            )
        except Exception as exc:  # noqa: BLE001 - surface any domain/service error to the user
            QMessageBox.warning(self, "تعذر حفظ الفاتورة", str(exc))
            return

        self._last_invoice_id = invoice_id
        self.print_button.setEnabled(True)
        self.export_button.setEnabled(True)
        invoice_no = invoices_repo.get_invoice(self._conn, invoice_id)["header"]["invoice_no"]
        QMessageBox.information(self, "تم الحفظ", f"تم إنشاء الفاتورة رقم {invoice_no}")
        self._reset_form()

    def _reset_form(self) -> None:
        self.customer_name_input.clear()
        self.phone_input.clear()
        self.tax_included_checkbox.setChecked(False)
        self.items_table.clear_rows()

    def _print_last(self) -> None:
        if self._last_invoice_id is None:
            return
        invoice = invoices_repo.get_invoice(self._conn, self._last_invoice_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        show_print_dialog(self, invoice, shop_name)

    def _export_last(self) -> None:
        if self._last_invoice_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "تصدير PDF", "invoice.pdf", "PDF (*.pdf)")
        if not path:
            return
        invoice = invoices_repo.get_invoice(self._conn, self._last_invoice_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        export_invoice_pdf(invoice, shop_name, path)
