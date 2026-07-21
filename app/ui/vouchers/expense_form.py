"""General expenses screen (مصاريف) / expense vouchers (سندات صرف)."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
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
from app.repositories import vouchers_repo
from app.services import voucher_service
from app.ui.widgets.money_spinbox import MoneySpinBox
from app.ui.widgets.override_dialog import prompt_override_password


class ExpenseFormScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("سندات الصرف والمصاريف العامة"))

        form = QFormLayout()
        self.description_input = QLineEdit()
        form.addRow("الوصف *", self.description_input)

        self.amount_input = MoneySpinBox()
        form.addRow("المبلغ *", self.amount_input)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        form.addRow("التاريخ", self.date_input)

        self.note_input = QLineEdit()
        form.addRow("ملاحظات", self.note_input)
        layout.addLayout(form)

        buttons_row = QHBoxLayout()
        save_button = QPushButton("حفظ سند الصرف")
        save_button.clicked.connect(self._save)
        buttons_row.addWidget(save_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["رقم السند", "الوصف", "المبلغ", "التاريخ"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self._refresh_table()

    def _save(self) -> None:
        try:
            voucher_service.create_expense(
                self._conn,
                self._user,
                description=self.description_input.text().strip(),
                amount_fils=self.amount_input.fils_value(),
                expense_date=self.date_input.date().toString("yyyy-MM-dd"),
                override_password_prompt=lambda: prompt_override_password("إنشاء سند صرف", self),
                note=self.note_input.text().strip() or None,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الحفظ", str(exc))
            return
        self.description_input.clear()
        self.amount_input.setValue(0)
        self.note_input.clear()
        self._refresh_table()

    def _refresh_table(self) -> None:
        rows = vouchers_repo.list_expenses(self._conn)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["voucher_no"]))
            self.table.setItem(i, 1, QTableWidgetItem(row["description"]))
            self.table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["amount_fils"])))
            self.table.setItem(i, 3, QTableWidgetItem(row["expense_date"]))
