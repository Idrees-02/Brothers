"""Employee withdrawals screen (سحوبات الموظفين)."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
from app.repositories import employees_repo
from app.services import employee_service
from app.ui.widgets.card import Card
from app.ui.widgets.money_spinbox import MoneySpinBox


class WithdrawalScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._employee_ids: list[int] = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("سحوبات الموظفين خلال الشهر")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.employee_combo = QComboBox()
        self.employee_combo.currentIndexChanged.connect(self._refresh_table)
        form.addRow("الموظف *", self.employee_combo)

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
        save_button = QPushButton("تسجيل السحب")
        save_button.clicked.connect(self._save)
        buttons_row.addWidget(save_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["المبلغ", "التاريخ", "ملاحظات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self._load_employees()

    def _load_employees(self) -> None:
        employees = employees_repo.list_employees(self._conn)
        self._employee_ids = [e["id"] for e in employees]
        self.employee_combo.clear()
        self.employee_combo.addItems([e["full_name"] for e in employees])

    def _current_employee_id(self) -> int | None:
        index = self.employee_combo.currentIndex()
        if index < 0 or index >= len(self._employee_ids):
            return None
        return self._employee_ids[index]

    def _save(self) -> None:
        employee_id = self._current_employee_id()
        if employee_id is None:
            QMessageBox.warning(self, "خطأ", "الرجاء اختيار موظف")
            return
        if self.amount_input.fils_value() <= 0:
            QMessageBox.warning(self, "خطأ", "المبلغ يجب أن يكون أكبر من صفر")
            return
        employee_service.add_withdrawal(
            self._conn,
            self._user,
            employee_id,
            self.amount_input.fils_value(),
            self.date_input.date().toString("yyyy-MM-dd"),
            note=self.note_input.text().strip() or None,
        )
        self.amount_input.setValue(0)
        self.note_input.clear()
        self._refresh_table()

    def _refresh_table(self) -> None:
        employee_id = self._current_employee_id()
        if employee_id is None:
            self.table.setRowCount(0)
            return
        rows = employees_repo.list_withdrawals(self._conn, employee_id, "0000-01-01", "9999-12-31")
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(fils_to_bhd_str(row["amount_fils"])))
            self.table.setItem(i, 1, QTableWidgetItem(row["withdrawal_date"]))
            self.table.setItem(i, 2, QTableWidgetItem(row["note"] or ""))
