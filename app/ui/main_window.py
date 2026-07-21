"""Main application shell: side navigation + a stacked content area."""

import sqlite3

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.employees.attendance_screen import AttendanceScreen
from app.ui.employees.employee_list import EmployeeListScreen
from app.ui.employees.salary_report_screen import SalaryReportScreen
from app.ui.employees.withdrawal_form import WithdrawalScreen
from app.ui.invoices.cash_invoice_form import CashInvoiceForm
from app.ui.invoices.installation_invoice_form import InstallationInvoiceForm
from app.ui.invoices.invoice_search import InvoiceSearchScreen
from app.ui.reports.tax_report_screen import TaxReportScreen
from app.ui.settings.settings_screen import SettingsScreen
from app.ui.vouchers.expense_form import ExpenseFormScreen
from app.ui.vouchers.purchase_invoice_form import PurchaseInvoiceFormScreen


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row):
        super().__init__()
        self._conn = conn
        self._user = user
        self.setWindowTitle("الإخوة لبيع السجاد - نظام الإدارة")
        self.resize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        self.nav_list.setFixedWidth(220)
        root_layout.addWidget(self.nav_list)

        right_side = QVBoxLayout()
        root_layout.addLayout(right_side)

        self.user_label = QLabel(f"مسجل الدخول: {user['display_name']}")
        self.user_label.setStyleSheet("padding: 6px; font-weight: bold;")
        right_side.addWidget(self.user_label)

        self.stack = QStackedWidget()
        right_side.addWidget(self.stack)

        self._pages: dict[str, QWidget] = {}
        self._build_pages()
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0)

    def _add_page(self, title: str, widget: QWidget) -> None:
        self._pages[title] = widget
        self.stack.addWidget(widget)
        QListWidgetItem(title, self.nav_list)

    def _build_pages(self) -> None:
        self._add_page("فاتورة قطع جاهزة", CashInvoiceForm(self._conn, self._user, self))
        self._add_page(
            "فاتورة تركيب وتفصيل", InstallationInvoiceForm(self._conn, self._user, self)
        )
        self._add_page("البحث عن الفواتير", InvoiceSearchScreen(self._conn, self._user, self))
        self._add_page("سندات الصرف", ExpenseFormScreen(self._conn, self._user, self))
        self._add_page("فواتير الشراء", PurchaseInvoiceFormScreen(self._conn, self._user, self))
        self._add_page("الموظفون", EmployeeListScreen(self._conn, self._user, self))
        self._add_page("الحضور والانصراف", AttendanceScreen(self._conn, self._user, self))
        self._add_page("سحوبات الموظفين", WithdrawalScreen(self._conn, self._user, self))
        self._add_page("تقرير الرواتب", SalaryReportScreen(self._conn, self._user, self))
        self._add_page("التقرير الضريبي", TaxReportScreen(self._conn, self._user, self))
        if self._user["is_admin"]:
            self._add_page("الإعدادات", SettingsScreen(self._conn, self._user, self))
