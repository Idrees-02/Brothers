"""Tax report screen (كشف ضريبي) - net sales/purchases and their tax, and
the net tax payable (tax collected on sales minus tax paid on purchases)."""

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
from app.repositories import reports_repo, settings_repo
from app.ui.vouchers.voucher_print import build_report_html, data_table_fragment, show_print_dialog_html
from app.ui.widgets.card import Card
from app.ui.widgets.date_range_picker import DateRangePicker

_TYPE_LABEL = {"cash": "قطع جاهزة", "installation": "تركيب وتفصيل"}


class _TaxSummaryBox(Card):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("dashboardStatCard")
        title_label = QLabel(title)
        title_label.setObjectName("sectionSubtitle")
        self.body_layout.addWidget(title_label)

        self.net_label = QLabel("0.000 د.ب")
        self.net_label.setObjectName("dashboardStatValue")
        self.body_layout.addWidget(self.net_label)

        self.tax_label = QLabel()
        self.body_layout.addWidget(self.tax_label)
        self.total_label = QLabel()
        self.body_layout.addWidget(self.total_label)

    def set_values(self, net_fils: int, tax_fils: int, total_fils: int) -> None:
        self.net_label.setText(f"{fils_to_bhd_str(net_fils)} د.ب")
        self.tax_label.setText(f"الضريبة: {fils_to_bhd_str(tax_fils)} د.ب")
        self.total_label.setText(f"الإجمالي: {fils_to_bhd_str(total_fils)} د.ب")


class TaxReportScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._start = self._end = ""

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("صافي المبيعات والمشتريات وضريبتهما، وصافي الضريبة المستحقة خلال فترة محددة")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

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

        boxes_row = QHBoxLayout()
        self.sales_box = _TaxSummaryBox("صافي المبيعات")
        self.purchases_box = _TaxSummaryBox("صافي المشتريات")
        boxes_row.addWidget(self.sales_box)
        boxes_row.addWidget(self.purchases_box)
        layout.addLayout(boxes_row)

        self.net_tax_label = QLabel()
        self.net_tax_label.setObjectName("statValueNet")
        layout.addWidget(self.net_tax_label)

        layout.addWidget(QLabel("تفاصيل فواتير المبيعات"))
        self.sales_table = QTableWidget(0, 6)
        self.sales_table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "النوع", "المبلغ الخاضع للضريبة", "نسبة الضريبة", "قيمة الضريبة", "الإجمالي"]
        )
        self.sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sales_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sales_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.sales_table)

        layout.addWidget(QLabel("تفاصيل فواتير المشتريات"))
        self.purchases_table = QTableWidget(0, 5)
        self.purchases_table.setHorizontalHeaderLabels(
            ["رقم السند", "المورد", "المبلغ الخاضع للضريبة", "قيمة الضريبة", "الإجمالي"]
        )
        self.purchases_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.purchases_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.purchases_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.purchases_table)

    def _generate(self) -> None:
        self._start = self.date_range.start_date_str()
        self._end = self.date_range.end_date_str()
        summary = reports_repo.tax_report_summary(self._conn, self._start, self._end)

        self.sales_box.set_values(
            summary["sales_subtotal_fils"], summary["sales_tax_fils"], summary["sales_total_fils"]
        )
        self.purchases_box.set_values(
            summary["purchases_subtotal_fils"],
            summary["purchases_tax_fils"],
            summary["purchases_total_fils"],
        )
        self.net_tax_label.setText(
            f"صافي الضريبة المستحقة: {fils_to_bhd_str(summary['net_tax_fils'])} د.ب"
        )

        sales_rows = reports_repo.tax_report_invoices(self._conn, self._start, self._end)
        self.sales_table.setRowCount(len(sales_rows))
        for i, row in enumerate(sales_rows):
            self.sales_table.setItem(i, 0, QTableWidgetItem(row["invoice_no"]))
            self.sales_table.setItem(
                i, 1, QTableWidgetItem(_TYPE_LABEL.get(row["invoice_type"], row["invoice_type"]))
            )
            self.sales_table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["subtotal_fils"])))
            self.sales_table.setItem(i, 3, QTableWidgetItem(f"{row['tax_rate_percent']}%"))
            self.sales_table.setItem(i, 4, QTableWidgetItem(fils_to_bhd_str(row["tax_amount_fils"])))
            self.sales_table.setItem(i, 5, QTableWidgetItem(fils_to_bhd_str(row["grand_total_fils"])))

        purchase_rows = reports_repo.tax_report_purchases(self._conn, self._start, self._end)
        self.purchases_table.setRowCount(len(purchase_rows))
        for i, row in enumerate(purchase_rows):
            self.purchases_table.setItem(i, 0, QTableWidgetItem(row["voucher_no"]))
            self.purchases_table.setItem(i, 1, QTableWidgetItem(row["supplier_name"]))
            self.purchases_table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["subtotal_fils"])))
            self.purchases_table.setItem(i, 3, QTableWidgetItem(fils_to_bhd_str(row["tax_amount_fils"])))
            self.purchases_table.setItem(i, 4, QTableWidgetItem(fils_to_bhd_str(row["total_amount_fils"])))

    def _print_report(self) -> None:
        if not self._start:
            self._generate()
        summary = reports_repo.tax_report_summary(self._conn, self._start, self._end)

        stats_fragment = data_table_fragment(
            ["البند", "الصافي", "الضريبة", "الإجمالي"],
            [
                [
                    "المبيعات",
                    f"{fils_to_bhd_str(summary['sales_subtotal_fils'])} د.ب",
                    f"{fils_to_bhd_str(summary['sales_tax_fils'])} د.ب",
                    f"{fils_to_bhd_str(summary['sales_total_fils'])} د.ب",
                ],
                [
                    "المشتريات",
                    f"{fils_to_bhd_str(summary['purchases_subtotal_fils'])} د.ب",
                    f"{fils_to_bhd_str(summary['purchases_tax_fils'])} د.ب",
                    f"{fils_to_bhd_str(summary['purchases_total_fils'])} د.ب",
                ],
            ],
        )
        net_tax_fragment = f"<h3>صافي الضريبة المستحقة: {fils_to_bhd_str(summary['net_tax_fils'])} د.ب</h3>"

        sales_rows = reports_repo.tax_report_invoices(self._conn, self._start, self._end)
        sales_fragment = data_table_fragment(
            ["رقم الفاتورة", "النوع", "المبلغ الخاضع للضريبة", "نسبة الضريبة", "قيمة الضريبة", "الإجمالي"],
            [
                [
                    row["invoice_no"],
                    _TYPE_LABEL.get(row["invoice_type"], row["invoice_type"]),
                    fils_to_bhd_str(row["subtotal_fils"]),
                    f"{row['tax_rate_percent']}%",
                    fils_to_bhd_str(row["tax_amount_fils"]),
                    fils_to_bhd_str(row["grand_total_fils"]),
                ]
                for row in sales_rows
            ],
        )

        purchase_rows = reports_repo.tax_report_purchases(self._conn, self._start, self._end)
        purchases_fragment = data_table_fragment(
            ["رقم السند", "المورد", "المبلغ الخاضع للضريبة", "قيمة الضريبة", "الإجمالي"],
            [
                [
                    row["voucher_no"],
                    row["supplier_name"],
                    fils_to_bhd_str(row["subtotal_fils"]),
                    fils_to_bhd_str(row["tax_amount_fils"]),
                    fils_to_bhd_str(row["total_amount_fils"]),
                ]
                for row in purchase_rows
            ],
        )

        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        html = build_report_html(
            shop_name,
            f"التقرير الضريبي: من {self._start} إلى {self._end}",
            [
                stats_fragment,
                net_tax_fragment,
                "<h3>فواتير المبيعات</h3>",
                sales_fragment,
                "<h3>فواتير المشتريات</h3>",
                purchases_fragment,
            ],
        )
        show_print_dialog_html(self, html)
