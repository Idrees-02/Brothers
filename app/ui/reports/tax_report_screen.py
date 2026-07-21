"""Tax report screen (كشف ضريبي)."""

import sqlite3

from PySide6.QtWidgets import (
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
from app.repositories import reports_repo
from app.ui.widgets.date_range_picker import DateRangePicker

_TYPE_LABEL = {"cash": "قطع جاهزة", "installation": "تركيب وتفصيل"}


class TaxReportScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("التقرير الضريبي"))

        controls_row = QHBoxLayout()
        self.date_range = DateRangePicker()
        controls_row.addWidget(self.date_range)
        generate_button = QPushButton("إنشاء التقرير")
        generate_button.clicked.connect(self._generate)
        controls_row.addWidget(generate_button)
        controls_row.addStretch()
        layout.addLayout(controls_row)

        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "النوع", "المبلغ الخاضع للضريبة", "نسبة الضريبة", "قيمة الضريبة", "الإجمالي"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def _generate(self) -> None:
        start = self.date_range.start_date_str()
        end = self.date_range.end_date_str()
        summary = reports_repo.tax_report_summary(self._conn, start, end)
        self.summary_label.setText(
            f"عدد الفواتير: {summary['invoice_count']} | "
            f"إجمالي المبالغ الخاضعة للضريبة: {fils_to_bhd_str(summary['total_subtotal_fils'])} د.ب | "
            f"إجمالي الضريبة المحصلة: {fils_to_bhd_str(summary['total_tax_fils'])} د.ب | "
            f"إجمالي المبيعات: {fils_to_bhd_str(summary['total_grand_fils'])} د.ب"
        )

        rows = reports_repo.tax_report_invoices(self._conn, start, end)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["invoice_no"]))
            self.table.setItem(
                i, 1, QTableWidgetItem(_TYPE_LABEL.get(row["invoice_type"], row["invoice_type"]))
            )
            self.table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["subtotal_fils"])))
            self.table.setItem(i, 3, QTableWidgetItem(f"{row['tax_rate_percent']}%"))
            self.table.setItem(i, 4, QTableWidgetItem(fils_to_bhd_str(row["tax_amount_fils"])))
            self.table.setItem(i, 5, QTableWidgetItem(fils_to_bhd_str(row["grand_total_fils"])))
