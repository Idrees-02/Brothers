"""Purchase invoices screen (فواتير شراء) - goods bought by the shop."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
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
from app.ui.widgets.account_combo import AccountCombo
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

        self.account_combo = AccountCombo(conn, allow_empty=True)
        form.addRow("الحساب", self.account_combo)

        self.invoice_kind_combo = QComboBox()
        self.invoice_kind_combo.addItem("نقدا", False)
        self.invoice_kind_combo.addItem("آجل", True)
        form.addRow("نوع الفاتورة", self.invoice_kind_combo)

        self.tax_rate_input = QDoubleSpinBox()
        self.tax_rate_input.setDecimals(2)
        self.tax_rate_input.setRange(0.0, 100.0)
        self.tax_rate_input.setSuffix(" %")
        self.tax_rate_input.setValue(settings_repo.get_settings(conn)["tax_rate_percent"])
        self.tax_rate_input.valueChanged.connect(lambda value: self.items_table.set_tax_rate(value))
        form.addRow("نسبة الضريبة", self.tax_rate_input)

        self.tax_included_checkbox = QCheckBox("المبلغ شامل الضريبة")
        self.tax_included_checkbox.stateChanged.connect(
            lambda: self.items_table.set_tax_included(self.tax_included_checkbox.isChecked())
        )
        form.addRow(self.tax_included_checkbox)
        layout.addLayout(form)

        self.items_table = LineItemsTable(quantity_label="الكمية", conn=conn)
        self.items_table.set_tax_rate(settings_repo.get_settings(conn)["tax_rate_percent"])
        self.tax_included_checkbox.setChecked(True)  # default: totals entered tax-inclusive
        self.items_table.add_row()
        layout.addWidget(self.items_table)

        buttons_row = QHBoxLayout()
        save_button = QPushButton("حفظ فاتورة الشراء")
        save_button.clicked.connect(self._save)
        buttons_row.addWidget(save_button)
        self.settle_button = QPushButton("تسديد الفاتورة المحددة")
        self.settle_button.setObjectName("secondaryButton")
        self.settle_button.clicked.connect(self._settle_selected)
        buttons_row.addWidget(self.settle_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["رقم السند", "المورد", "الضريبة", "الإجمالي شامل الضريبة", "النوع", "الحالة", "التاريخ"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self._rows: list[sqlite3.Row] = []
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
                tax_rate_percent=self.tax_rate_input.value(),
                account_id=self.account_combo.selected_account_id(),
                is_credit=bool(self.invoice_kind_combo.currentData()),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الحفظ", str(exc))
            return
        self.supplier_input.clear()
        self.note_input.clear()
        self.tax_included_checkbox.setChecked(True)
        self.tax_rate_input.setValue(settings_repo.get_settings(self._conn)["tax_rate_percent"])
        self.invoice_kind_combo.setCurrentIndex(0)
        self.account_combo.refresh()
        self.account_combo.setCurrentIndex(0)
        self.items_table.clear_rows()
        self.items_table.add_row()
        self._refresh_table()

    def _settle_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, "تنبيه", "الرجاء تحديد فاتورة من الجدول أولاً")
            return
        try:
            voucher_service.settle_purchase_invoice(
                self._conn,
                self._user,
                self._rows[row]["id"],
                override_password_prompt=lambda: prompt_override_password(
                    "تسديد فاتورة شراء آجلة", self
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر التسديد", str(exc))
            return
        QMessageBox.information(self, "تم", "تم تسديد الفاتورة - ستظهر الآن في التقرير المالي")
        self._refresh_table()

    def _refresh_table(self) -> None:
        self._rows = vouchers_repo.list_purchase_invoices(self._conn)
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            if row["is_credit"]:
                status = "مسددة" if row["paid_at"] else "غير مسددة"
            else:
                status = "مدفوعة"
            self.table.setItem(i, 0, QTableWidgetItem(row["voucher_no"]))
            self.table.setItem(i, 1, QTableWidgetItem(row["supplier_name"]))
            self.table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["tax_amount_fils"])))
            self.table.setItem(i, 3, QTableWidgetItem(fils_to_bhd_str(row["total_amount_fils"])))
            self.table.setItem(i, 4, QTableWidgetItem("آجل" if row["is_credit"] else "نقدا"))
            self.table.setItem(i, 5, QTableWidgetItem(status))
            self.table.setItem(i, 6, QTableWidgetItem(row["purchase_date"]))
