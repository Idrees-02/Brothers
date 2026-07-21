"""Daily attendance roll-call (الحضور والانصراف) - present/absent/late per
employee for a chosen day (defaults to today, matching the morning
check-in workflow)."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories import employees_repo
from app.services import employee_service
from app.ui.widgets.override_dialog import prompt_override_password

_STATUS_OPTIONS = [("present", "حضور"), ("absent", "غياب"), ("late", "تأخير")]
_STATUS_LABELS = {key: label for key, label in _STATUS_OPTIONS}
_LABEL_TO_STATUS = {label: key for key, label in _STATUS_OPTIONS}


class AttendanceScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._employee_ids: list[int] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("تسجيل الحضور والانصراف اليومي"))

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("التاريخ:"))
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.dateChanged.connect(self._load_day)
        date_row.addWidget(self.date_input)
        date_row.addStretch()
        layout.addLayout(date_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["الموظف", "الحالة"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        save_button = QPushButton("حفظ الحضور")
        save_button.clicked.connect(self._save)
        layout.addWidget(save_button)

        self._load_day()

    def _load_day(self) -> None:
        work_date = self.date_input.date().toString("yyyy-MM-dd")
        employees = employees_repo.list_employees(self._conn)
        self._employee_ids = [e["id"] for e in employees]
        self.table.setRowCount(len(employees))
        for i, employee in enumerate(employees):
            self.table.setItem(i, 0, QTableWidgetItem(employee["full_name"]))

            combo = QComboBox()
            combo.addItems([label for _, label in _STATUS_OPTIONS])
            existing = employees_repo.get_attendance(self._conn, employee["id"], work_date)
            if existing:
                combo.setCurrentText(_STATUS_LABELS[existing["status"]])
            self.table.setCellWidget(i, 1, combo)

    def _save(self) -> None:
        work_date = self.date_input.date().toString("yyyy-MM-dd")
        try:
            for i, employee_id in enumerate(self._employee_ids):
                combo: QComboBox = self.table.cellWidget(i, 1)
                status = _LABEL_TO_STATUS[combo.currentText()]
                employee_service.register_attendance(
                    self._conn,
                    self._user,
                    employee_id,
                    work_date,
                    status,
                    override_password_prompt=lambda: prompt_override_password(
                        "تسجيل الحضور والانصراف", self
                    ),
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الحفظ", str(exc))
            return
        QMessageBox.information(self, "تم", "تم حفظ الحضور بنجاح")
