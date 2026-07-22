"""Purchase invoices screen (فواتير شراء) - goods bought by the shop."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDateEdit,
    QFormLayout,
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
from app.repositories import settings_repo, vouchers_repo
from app.services import voucher_service
from app.ui.widgets.card import Card, scrollable
from app.ui.widgets.line_items_table import LineItemsTable
from app.ui.widgets.override_dialog import prompt_override_password


class PurchaseInvoiceFormScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(scrollable(card))
        layout = card.body_layout

        subtitle = QLabel("البضائع المشتراة من قبل المحل")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.supplier_input = QLineEdit()
        form.addRow("اسم المورد *", self.supplier_input)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        form.addRow("التاريخ", self.date_input)

        self.note_input = QLineEdit()
        form.addRow("ملاحظات", self.note_input)

        self.tax_included_checkbox = QCheckBox("المبلغ شامل الضريبة")
        self.tax_included_checkbox.stateChanged.connect(
            lambda: self.items_table.set_tax_included(self.tax_included_checkbox.isChecked())
        )
        form.addRow(self.tax_included_checkbox)
        layout.addLayout(form)

        self.items_table = LineItemsTable(quantity_label="الكمية", conn=conn)
        self.items_table.set_tax_rate(settings_repo.get_settings(conn)["tax_rate_percent"])
        layout.addWidget(self.items_table)

        buttons_row = QHBoxLayout()
        save_button = QPushButton("حفظ فاتورة الشراء")
        save_button.clicked.connect(self._save)
        buttons_row.addWidget(save_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["رقم السند", "المورد", "الضريبة", "الإجمالي شامل الضريبة", "التاريخ"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self._refresh_table()

    def _save(self) -> None:
        items = self.items_table.items()
        try:
            voucher_service.create_purchase_invoice(
                self._conn,
                self._user,
                supplier_name=self.supplier_input.text().strip(),
                purchase_date=self.date_input.date().toString("yyyy-MM-dd"),
                items=items,
                override_password_prompt=lambda: prompt_override_password(
                    "إنشاء فاتورة شراء", self
                ),
                # The table always yields ex-tax unit prices regardless of
                # the entry-mode checkbox, so tax must be added on top.
                tax_included=False,
                note=self.note_input.text().strip() or None,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الحفظ", str(exc))
            return
        self.supplier_input.clear()
        self.note_input.clear()
        self.tax_included_checkbox.setChecked(False)
        self.items_table.clear_rows()
        self._refresh_table()

    def _refresh_table(self) -> None:
        rows = vouchers_repo.list_purchase_invoices(self._conn)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["voucher_no"]))
            self.table.setItem(i, 1, QTableWidgetItem(row["supplier_name"]))
            self.table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["tax_amount_fils"])))
            self.table.setItem(i, 3, QTableWidgetItem(fils_to_bhd_str(row["total_amount_fils"])))
            self.table.setItem(i, 4, QTableWidgetItem(row["purchase_date"]))
