"""Daily/weekly/monthly financial report: compact income/expense summary
plus a detailed record-by-record ledger of every invoice, remaining-balance
collection, expense, receipt, and purchase invoice in the period."""

import sqlite3
from datetime import date, timedelta

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
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
from app.repositories import reports_repo, settings_repo
from app.ui.vouchers.voucher_print import build_report_html, data_table_fragment, key_value_table_fragment, show_print_dialog_html
from app.ui.widgets.card import Card
from app.ui.widgets.date_range_picker import DateRangePicker

_KIND_LABEL = {
    "invoice": "فاتورة",
    "remaining_payment": "سداد متبقي",
    "expense": "سند صرف",
    "receipt": "سند قبض",
    "purchase": "فاتورة شراء",
}
_KIND_SIGN = {
    "invoice": "+",
    "remaining_payment": "+",
    "receipt": "+",
    "expense": "-",
    "purchase": "-",
}


class _StatBox(QWidget):
    def __init__(self, title: str, value_object_name: str = "statValueCompact"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("sectionSubtitle")
        layout.addWidget(title_label)
        self.value_label = QLabel("0.000 د.ب")
        self.value_label.setObjectName(value_object_name)
        layout.addWidget(self.value_label)

    def set_value(self, fils: int) -> None:
        self.value_label.setText(f"{fils_to_bhd_str(fils)} د.ب")


class FinancialReportScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("تقرير مالي شامل للمدخول والمصروفات خلال فترة محددة")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        presets_row = QHBoxLayout()
        for label, handler in (
            ("اليوم", self._preset_today),
            ("هذا الأسبوع", self._preset_this_week),
            ("هذا الشهر", self._preset_this_month),
        ):
            button = QPushButton(label)
            button.setObjectName("secondaryButton")
            button.clicked.connect(handler)
            presets_row.addWidget(button)
        presets_row.addStretch()
        layout.addLayout(presets_row)

        controls_row = QHBoxLayout()
        self.date_range = DateRangePicker()
        controls_row.addWidget(self.date_range)
        generate_button = QPushButton("إنشاء التقرير")
        generate_button.clicked.connect(self._generate)
        controls_row.addWidget(generate_button)
        print_button = QPushButton("طباعة التقرير")
        print_button.setObjectName("secondaryButton")
        print_button.clicked.connect(self._print_report)
        controls_row.addWidget(print_button)
        controls_row.addStretch()
        layout.addLayout(controls_row)

        stats_grid = QGridLayout()
        stats_grid.setHorizontalSpacing(28)
        stats_grid.setVerticalSpacing(8)

        self.invoice_income_box = _StatBox("مدخول الفواتير")
        self.receipt_income_box = _StatBox("سندات القبض")
        self.total_income_box = _StatBox("إجمالي المدخول", "statValueCompactPositive")
        self.expense_box = _StatBox("المصاريف")
        self.purchase_box = _StatBox("فواتير الشراء")
        self.total_expense_box = _StatBox("إجمالي المصروفات", "statValueCompactNegative")
        self.net_box = _StatBox("الصافي", "statValueCompactNet")

        stats_grid.addWidget(self.invoice_income_box, 0, 0)
        stats_grid.addWidget(self.receipt_income_box, 0, 1)
        stats_grid.addWidget(self.total_income_box, 0, 2)
        stats_grid.addWidget(self.expense_box, 1, 0)
        stats_grid.addWidget(self.purchase_box, 1, 1)
        stats_grid.addWidget(self.total_expense_box, 1, 2)
        stats_grid.addWidget(self.net_box, 1, 3)

        layout.addLayout(stats_grid)

        layout.addWidget(QLabel("كشف الحركات التفصيلي"))
        self.ledger_table = QTableWidget(0, 5)
        self.ledger_table.setHorizontalHeaderLabels(["النوع", "المرجع", "الوصف", "المبلغ", "التاريخ"])
        self.ledger_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ledger_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ledger_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.ledger_table)

        self._preset_today()

    def _apply_range(self, start: date, end: date) -> None:
        self.date_range.from_date.setDate(QDate(start.year, start.month, start.day))
        self.date_range.to_date.setDate(QDate(end.year, end.month, end.day))
        self._generate()

    def _preset_today(self) -> None:
        today = date.today()
        self._apply_range(today, today)

    def _preset_this_week(self) -> None:
        today = date.today()
        start = today - timedelta(days=today.weekday())
        self._apply_range(start, today)

    def _preset_this_month(self) -> None:
        today = date.today()
        start = today.replace(day=1)
        self._apply_range(start, today)

    def _generate(self) -> None:
        start = self.date_range.start_date_str()
        end = self.date_range.end_date_str()
        summary = reports_repo.period_financial_summary(self._conn, start, end)

        self.invoice_income_box.set_value(summary["invoice_income_fils"])
        self.receipt_income_box.set_value(summary["receipt_income_fils"])
        self.total_income_box.set_value(summary["total_income_fils"])
        self.expense_box.set_value(summary["expense_fils"])
        self.purchase_box.set_value(summary["purchase_fils"])
        self.total_expense_box.set_value(summary["total_expense_fils"])
        self.net_box.set_value(summary["net_fils"])

        ledger = reports_repo.period_transaction_ledger(self._conn, start, end)
        self.ledger_table.setRowCount(len(ledger))
        for i, record in enumerate(ledger):
            self.ledger_table.setItem(
                i, 0, QTableWidgetItem(_KIND_LABEL.get(record["kind"], record["kind"]))
            )
            self.ledger_table.setItem(i, 1, QTableWidgetItem(record["reference"]))
            self.ledger_table.setItem(i, 2, QTableWidgetItem(record["description"]))
            sign = _KIND_SIGN.get(record["kind"], "")
            self.ledger_table.setItem(
                i, 3, QTableWidgetItem(f"{sign}{fils_to_bhd_str(record['amount_fils'])}")
            )
            self.ledger_table.setItem(i, 4, QTableWidgetItem(record["txn_date"]))

    def _print_report(self) -> None:
        start = self.date_range.start_date_str()
        end = self.date_range.end_date_str()
        summary = reports_repo.period_financial_summary(self._conn, start, end)
        ledger = reports_repo.period_transaction_ledger(self._conn, start, end)

        stats_fragment = key_value_table_fragment(
            [
                ("مدخول الفواتير", f"{fils_to_bhd_str(summary['invoice_income_fils'])} د.ب"),
                ("سندات القبض", f"{fils_to_bhd_str(summary['receipt_income_fils'])} د.ب"),
                ("إجمالي المدخول", f"{fils_to_bhd_str(summary['total_income_fils'])} د.ب"),
                ("المصاريف", f"{fils_to_bhd_str(summary['expense_fils'])} د.ب"),
                ("فواتير الشراء", f"{fils_to_bhd_str(summary['purchase_fils'])} د.ب"),
                ("إجمالي المصروفات", f"{fils_to_bhd_str(summary['total_expense_fils'])} د.ب"),
                ("الصافي", f"{fils_to_bhd_str(summary['net_fils'])} د.ب"),
            ]
        )
        ledger_fragment = data_table_fragment(
            ["النوع", "المرجع", "الوصف", "المبلغ", "التاريخ"],
            [
                [
                    _KIND_LABEL.get(record["kind"], record["kind"]),
                    record["reference"],
                    record["description"],
                    f"{_KIND_SIGN.get(record['kind'], '')}{fils_to_bhd_str(record['amount_fils'])}",
                    record["txn_date"],
                ]
                for record in ledger
            ],
        )

        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        html = build_report_html(
            shop_name,
            f"التقرير المالي: من {start} إلى {end}",
            [stats_fragment, ledger_fragment],
        )
        show_print_dialog_html(self, html)
