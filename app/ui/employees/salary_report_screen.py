"""End-of-month salary report screen - per-employee breakdown of final pay."""

import sqlite3

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.money import fils_to_bhd_str
from app.services import employee_service
from app.ui.widgets.card import Card
from app.ui.widgets.date_range_picker import DateRangePicker


class SalaryReportScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("تقرير الرواتب الشهري لكل الموظفين")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        controls_row = QHBoxLayout()
        self.date_range = DateRangePicker()
        controls_row.addWidget(self.date_range)
        generate_button = QPushButton("إنشاء التقرير")
        generate_button.clicked.connect(self._generate)
        controls_row.addWidget(generate_button)
        controls_row.addStretch()
        layout.addLayout(controls_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["الموظف", "الراتب الأساسي", "السحوبات", "خصم الغياب", "خصم التأخير", "الصافي المستحق"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

    def _generate(self) -> None:
        start = self.date_range.start_date_str()
        end = self.date_range.end_date_str()
        results = employee_service.generate_salary_report_all(self._conn, start, end)
        self.table.setRowCount(len(results))
        for i, (employee, breakdown) in enumerate(results):
            self.table.setItem(i, 0, QTableWidgetItem(employee["full_name"]))
            self.table.setItem(i, 1, QTableWidgetItem(fils_to_bhd_str(breakdown.base_salary_fils)))
            self.table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(breakdown.withdrawals_fils)))
            self.table.setItem(i, 3, QTableWidgetItem(fils_to_bhd_str(breakdown.absence_deduction_fils)))
            self.table.setItem(i, 4, QTableWidgetItem(fils_to_bhd_str(breakdown.late_deduction_fils)))
            self.table.setItem(i, 5, QTableWidgetItem(fils_to_bhd_str(breakdown.final_pay_fils)))
