"""Simple from/to date range picker used by the tax report and salary report screens."""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit, QHBoxLayout, QLabel, QWidget


class DateRangePicker(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        today = QDate.currentDate()
        first_of_month = QDate(today.year(), today.month(), 1)

        layout.addWidget(QLabel("من:"))
        self.from_date = QDateEdit(first_of_month)
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.from_date)

        layout.addWidget(QLabel("إلى:"))
        self.to_date = QDateEdit(today)
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self.to_date)

    def start_date_str(self) -> str:
        return self.from_date.date().toString("yyyy-MM-dd")

    def end_date_str(self) -> str:
        return self.to_date.date().toString("yyyy-MM-dd")
