"""Invoice search screen - search by invoice number, customer name, phone,
or address, then view/print/collect-remaining-payment/void from a detail
dialog.
"""

import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.money import fils_to_bhd_str
from app.repositories import invoices_repo, settings_repo
from app.services import invoice_service
from app.ui.invoices.invoice_print import export_invoice_pdf, show_print_dialog
from app.ui.widgets.override_dialog import prompt_override_password

_STATUS_LABEL = {"booked": "محجوزة", "completed": "مكتملة", "voided": "ملغاة"}
_TYPE_LABEL = {"cash": "قطع جاهزة", "installation": "تركيب وتفصيل"}


class InvoiceDetailDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, invoice_id: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._invoice_id = invoice_id
        self.setWindowTitle("تفاصيل الفاتورة")
        self.resize(420, 400)

        self.layout_ = QVBoxLayout(self)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.layout_.addWidget(self.info_label)

        buttons_row = QHBoxLayout()
        print_button = QPushButton("طباعة")
        print_button.clicked.connect(self._print)
        buttons_row.addWidget(print_button)

        export_button = QPushButton("تصدير PDF")
        export_button.clicked.connect(self._export)
        buttons_row.addWidget(export_button)

        self.collect_button = QPushButton("تحصيل المتبقي")
        self.collect_button.clicked.connect(self._collect_remaining)
        buttons_row.addWidget(self.collect_button)

        self.void_button = QPushButton("إلغاء الفاتورة")
        self.void_button.setObjectName("dangerButton")
        self.void_button.clicked.connect(self._void)
        buttons_row.addWidget(self.void_button)

        self.layout_.addLayout(buttons_row)
        self._refresh()

    def _refresh(self) -> None:
        invoice = invoices_repo.get_invoice(self._conn, self._invoice_id)
        header = invoice["header"]
        paid = sum(p["amount_fils"] for p in invoice["payments"])
        remaining = header["grand_total_fils"] - paid
        self.info_label.setText(
            f"رقم الفاتورة: {header['invoice_no']}\n"
            f"النوع: {_TYPE_LABEL.get(header['invoice_type'], header['invoice_type'])}\n"
            f"الزبون: {header['customer_name'] or ''}\n"
            f"الهاتف: {header['phone']}\n"
            f"العنوان: {header['address'] or ''}\n"
            f"المنطقة: {header['area_region'] or ''}\n"
            f"الحالة: {_STATUS_LABEL.get(header['status'], header['status'])}\n"
            f"الإجمالي: {fils_to_bhd_str(header['grand_total_fils'])} د.ب\n"
            f"المدفوع: {fils_to_bhd_str(paid)} د.ب\n"
            f"المتبقي: {fils_to_bhd_str(remaining)} د.ب"
        )
        self.collect_button.setEnabled(header["status"] == "booked" and remaining > 0)
        self.void_button.setEnabled(header["status"] != "voided")

    def _print(self) -> None:
        invoice = invoices_repo.get_invoice(self._conn, self._invoice_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        show_print_dialog(self, invoice, shop_name)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "تصدير PDF", "invoice.pdf", "PDF (*.pdf)")
        if not path:
            return
        invoice = invoices_repo.get_invoice(self._conn, self._invoice_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        export_invoice_pdf(invoice, shop_name, path)

    def _collect_remaining(self) -> None:
        try:
            invoice_service.record_remaining_payment(
                self._conn,
                self._user,
                self._invoice_id,
                override_password_prompt=lambda: prompt_override_password(
                    "تحصيل المبلغ المتبقي", self
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر التحصيل", str(exc))
            return
        self._refresh()

    def _void(self) -> None:
        confirm = QMessageBox.question(
            self, "تأكيد الإلغاء", "هل أنت متأكد من إلغاء هذه الفاتورة؟"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            invoice_service.void_invoice(
                self._conn,
                self._user,
                self._invoice_id,
                override_password_prompt=lambda: prompt_override_password("إلغاء فاتورة", self),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الإلغاء", str(exc))
            return
        self._refresh()


class InvoiceSearchScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._result_ids: list[int] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("البحث برقم الفاتورة أو اسم الزبون أو الهاتف أو العنوان"))

        search_row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.returnPressed.connect(self._search)
        search_row.addWidget(self.query_input)
        search_button = QPushButton("بحث")
        search_button.clicked.connect(self._search)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "النوع", "الزبون", "الهاتف", "الحالة", "الإجمالي"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.results_table)

    def _search(self) -> None:
        query = self.query_input.text().strip()
        rows = invoice_service.search_invoices(self._conn, query) if query else []
        self._result_ids = [row["id"] for row in rows]
        self.results_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.results_table.setItem(i, 0, QTableWidgetItem(row["invoice_no"]))
            self.results_table.setItem(
                i, 1, QTableWidgetItem(_TYPE_LABEL.get(row["invoice_type"], row["invoice_type"]))
            )
            self.results_table.setItem(i, 2, QTableWidgetItem(row["customer_name"] or ""))
            self.results_table.setItem(i, 3, QTableWidgetItem(row["phone"]))
            self.results_table.setItem(
                i, 4, QTableWidgetItem(_STATUS_LABEL.get(row["status"], row["status"]))
            )
            self.results_table.setItem(i, 5, QTableWidgetItem(fils_to_bhd_str(row["grand_total_fils"])))

    def _open_selected(self) -> None:
        row = self.results_table.currentRow()
        if row < 0 or row >= len(self._result_ids):
            return
        dialog = InvoiceDetailDialog(self._conn, self._user, self._result_ids[row], self)
        dialog.exec()
        self._search()
