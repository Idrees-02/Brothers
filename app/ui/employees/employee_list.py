"""Employee list + create screen."""

import sqlite3

from PySide6.QtWidgets import (
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
from app.ui.widgets.money_spinbox import MoneySpinBox


class EmployeeListScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("الموظفون"))

        form = QFormLayout()
        self.full_name_input = QLineEdit()
        form.addRow("الاسم *", self.full_name_input)

        self.phone_input = QLineEdit()
        form.addRow("الهاتف", self.phone_input)

        self.base_salary_input = MoneySpinBox()
        form.addRow("الراتب الأساسي *", self.base_salary_input)
        layout.addLayout(form)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("إضافة موظف")
        add_button.clicked.connect(self._add_employee)
        buttons_row.addWidget(add_button)

        deactivate_button = QPushButton("إيقاف تفعيل المحدد")
        deactivate_button.setObjectName("dangerButton")
        deactivate_button.clicked.connect(self._deactivate_selected)
        buttons_row.addWidget(deactivate_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["الاسم", "الهاتف", "الراتب الأساسي"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self._employee_ids: list[int] = []
        self._refresh_table()

    def _add_employee(self) -> None:
        full_name = self.full_name_input.text().strip()
        if not full_name:
            QMessageBox.warning(self, "خطأ", "اسم الموظف مطلوب")
            return
        if self.base_salary_input.fils_value() <= 0:
            QMessageBox.warning(self, "خطأ", "الراتب الأساسي يجب أن يكون أكبر من صفر")
            return
        employees_repo.create_employee(
            self._conn,
            full_name,
            self.base_salary_input.fils_value(),
            phone=self.phone_input.text().strip() or None,
        )
        self.full_name_input.clear()
        self.phone_input.clear()
        self.base_salary_input.setValue(0)
        self._refresh_table()

    def _deactivate_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._employee_ids):
            return
        employees_repo.set_active(self._conn, self._employee_ids[row], False)
        self._refresh_table()

    def _refresh_table(self) -> None:
        rows = employees_repo.list_employees(self._conn)
        self._employee_ids = [row["id"] for row in rows]
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["full_name"]))
            self.table.setItem(i, 1, QTableWidgetItem(row["phone"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["base_salary_fils"])))
