"""Invoice statement screen (كشوفات الفواتير) - lists every invoice by
default (no search query required), with an optional date-range filter."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.money import fils_to_bhd_str
from app.repositories import invoices_repo, settings_repo
from app.services import invoice_service
from app.ui.invoices.invoice_detail_dialog import InvoiceDetailDialog
from app.ui.vouchers.voucher_print import build_table_html, show_print_dialog_html
from app.ui.widgets.card import Card
from app.ui.widgets.date_range_picker import DateRangePicker

_STATUS_LABEL = {"booked": "محجوزة", "completed": "مكتملة", "voided": "ملغاة"}
_TYPE_LABEL = {"cash": "قطع جاهزة", "installation": "تركيب وتفصيل"}


class InvoiceStatementScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._result_ids: list[int] = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("كشف بجميع الفواتير - يمكن البحث أو التصفية حسب التاريخ")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث برقم الفاتورة أو اسم الزبون أو الهاتف أو العنوان")
        self.search_input.returnPressed.connect(self._search)
        search_row.addWidget(self.search_input)
        search_button = QPushButton("بحث")
        search_button.clicked.connect(self._search)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)

        filter_row = QHBoxLayout()
        self.date_range = DateRangePicker()
        filter_row.addWidget(self.date_range)
        filter_button = QPushButton("تصفية حسب التاريخ")
        filter_button.clicked.connect(self._filter_by_date)
        filter_row.addWidget(filter_button)
        show_all_button = QPushButton("عرض الكل")
        show_all_button.setObjectName("secondaryButton")
        show_all_button.clicked.connect(self._show_all)
        filter_row.addWidget(show_all_button)
        unpaid_button = QPushButton("الفواتير غير المسددة")
        unpaid_button.setObjectName("secondaryButton")
        unpaid_button.clicked.connect(self._show_unpaid)
        filter_row.addWidget(unpaid_button)
        print_button = QPushButton("طباعة الكشف")
        print_button.setObjectName("secondaryButton")
        print_button.clicked.connect(self._print_statement)
        filter_row.addWidget(print_button)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "النوع", "الزبون", "الهاتف", "الحالة", "الإجمالي", "المتبقي"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.table)

        self._show_all()

    def _populate(self, rows) -> None:
        self._result_ids = [row["id"] for row in rows]
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["invoice_no"]))
            self.table.setItem(
                i, 1, QTableWidgetItem(_TYPE_LABEL.get(row["invoice_type"], row["invoice_type"]))
            )
            self.table.setItem(i, 2, QTableWidgetItem(row["customer_name"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(row["phone"]))
            self.table.setItem(
                i, 4, QTableWidgetItem(_STATUS_LABEL.get(row["status"], row["status"]))
            )
            self.table.setItem(i, 5, QTableWidgetItem(fils_to_bhd_str(row["grand_total_fils"])))
            paid = sum(p["amount_fils"] for p in invoices_repo.get_invoice(self._conn, row["id"])["payments"])
            remaining = row["grand_total_fils"] - paid
            self.table.setItem(i, 6, QTableWidgetItem(fils_to_bhd_str(remaining)))

    def _show_all(self) -> None:
        self.search_input.clear()
        self._populate(invoice_service.list_all_invoices(self._conn))

    def _show_unpaid(self) -> None:
        self.search_input.clear()
        self._populate(invoices_repo.list_unpaid_invoices(self._conn))

    def _search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self._show_all()
            return
        self._populate(invoice_service.search_invoices(self._conn, query))

    def _filter_by_date(self) -> None:
        start = self.date_range.start_date_str()
        end = self.date_range.end_date_str()
        self._populate(invoices_repo.list_invoices_between(self._conn, start, end, exclude_voided=False))

    def show_for_date(self, target_date: QDate) -> None:
        """Entry point for the dashboard's "invoices today" stat card - jumps
        straight to that single day's invoices."""
        self.search_input.clear()
        self.date_range.set_range(target_date, target_date)
        self._filter_by_date()

    def _print_statement(self) -> None:
        """Prints exactly what's currently on screen (whichever filter -
        search/date range/unpaid/all - was last applied), read straight off
        the table rather than re-deriving it from a parallel data structure."""
        headers = [
            self.table.horizontalHeaderItem(col).text() for col in range(self.table.columnCount())
        ]
        rows = [
            [
                self.table.item(row, col).text() if self.table.item(row, col) else ""
                for col in range(self.table.columnCount())
            ]
            for row in range(self.table.rowCount())
        ]
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        html = build_table_html(shop_name, "كشف الفواتير", headers, rows)
        show_print_dialog_html(self, html)

    def _open_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._result_ids):
            return
        dialog = InvoiceDetailDialog(self._conn, self._user, self._result_ids[row], self)
        dialog.exec()
        if self.search_input.text().strip():
            self._search()
        else:
            self._show_all()
