"""Employee list + create screen."""

import sqlite3

from PySide6.QtWidgets import (
    QAbstractItemView,
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
from app.ui.widgets.card import Card
from app.ui.widgets.money_spinbox import MoneySpinBox


class EmployeeListScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._editing_id: int | None = None  # None = "add new employee" mode

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("إضافة موظف جديد وإدارة قائمة الموظفين - انقر مرتين على موظف لتعديل بياناته")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.full_name_input = QLineEdit()
        form.addRow("الاسم *", self.full_name_input)

        self.phone_input = QLineEdit()
        form.addRow("الهاتف", self.phone_input)

        self.base_salary_input = MoneySpinBox()
        form.addRow("الراتب الأساسي *", self.base_salary_input)
        layout.addLayout(form)

        buttons_row = QHBoxLayout()
        self.save_button = QPushButton("إضافة موظف")
        self.save_button.clicked.connect(self._save)
        buttons_row.addWidget(self.save_button)

        self.cancel_edit_button = QPushButton("إلغاء التعديل")
        self.cancel_edit_button.setObjectName("secondaryButton")
        self.cancel_edit_button.clicked.connect(self._cancel_edit)
        self.cancel_edit_button.setEnabled(False)
        buttons_row.addWidget(self.cancel_edit_button)

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
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._load_selected_for_edit)
        layout.addWidget(self.table)

        self._employee_ids: list[int] = []
        self._refresh_table()

    def _save(self) -> None:
        full_name = self.full_name_input.text().strip()
        if not full_name:
            QMessageBox.warning(self, "خطأ", "اسم الموظف مطلوب")
            return
        if self.base_salary_input.fils_value() <= 0:
            QMessageBox.warning(self, "خطأ", "الراتب الأساسي يجب أن يكون أكبر من صفر")
            return
        if self._editing_id is None:
            employees_repo.create_employee(
                self._conn,
                full_name,
                self.base_salary_input.fils_value(),
                phone=self.phone_input.text().strip() or None,
            )
        else:
            employees_repo.update_employee(
                self._conn,
                self._editing_id,
                full_name=full_name,
                base_salary_fils=self.base_salary_input.fils_value(),
                phone=self.phone_input.text().strip() or None,
            )
        self._cancel_edit()
        self._refresh_table()

    def _load_selected_for_edit(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._employee_ids):
            return
        employee = employees_repo.get_employee(self._conn, self._employee_ids[row])
        if employee is None:
            return
        self._editing_id = employee["id"]
        self.full_name_input.setText(employee["full_name"])
        self.phone_input.setText(employee["phone"] or "")
        self.base_salary_input.set_fils_value(employee["base_salary_fils"])
        self.save_button.setText("حفظ التعديلات")
        self.cancel_edit_button.setEnabled(True)

    def _cancel_edit(self) -> None:
        self._editing_id = None
        self.full_name_input.clear()
        self.phone_input.clear()
        self.base_salary_input.setValue(0)
        self.save_button.setText("إضافة موظف")
        self.cancel_edit_button.setEnabled(False)

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
