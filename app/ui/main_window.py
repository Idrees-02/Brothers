"""Main application shell: navy sidebar navigation + an animated stacked
content area with a page header."""

import sqlite3

from PySide6.QtCore import QDate, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import resources_dir
from app.repositories import settings_repo
from app.ui.dashboard_screen import DashboardScreen
from app.ui.employees.attendance_screen import AttendanceScreen
from app.ui.employees.employee_list import EmployeeListScreen
from app.ui.employees.salary_report_screen import SalaryReportScreen
from app.ui.employees.withdrawal_form import WithdrawalScreen
from app.ui.inventory.inventory_tab_screen import InventoryTabScreen
from app.ui.invoices.installation_schedule_screen import InstallationScheduleScreen
from app.ui.invoices.invoice_statement_screen import InvoiceStatementScreen
from app.ui.invoices.invoices_screen import InvoicesScreen
from app.ui.reports.accounts_statement_screen import AccountsStatementScreen
from app.ui.reports.financial_report_screen import FinancialReportScreen
from app.ui.reports.tax_report_screen import TaxReportScreen
from app.ui.settings.settings_screen import SettingsScreen
from app.ui.vouchers.expense_form import ExpenseFormScreen
from app.ui.vouchers.purchase_invoice_form import PurchaseInvoiceFormScreen
from app.ui.vouchers.receipt_form import ReceiptFormScreen
from app.ui.widgets.nav_sidebar import NavSidebar

_ICONS_DIR = resources_dir() / "icons"
_TRANSITION_BG = "#f4f6fb"


class MainWindow(QMainWindow):
    logout_requested = Signal()

    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row):
        super().__init__()
        self._conn = conn
        self._user = user
        shop_name = settings_repo.get_settings(conn)["shop_name_ar"]
        self.setWindowTitle(f"{shop_name} - نظام الإدارة")
        self.resize(1180, 740)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = NavSidebar(shop_name, f"مسجل الدخول: {user['display_name']}")
        root_layout.addWidget(self.sidebar)

        self._content_container = content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(28, 22, 28, 22)
        content_layout.setSpacing(14)
        root_layout.addWidget(content_container, 1)

        title_row = QHBoxLayout()
        self.home_button = QPushButton()
        home_icon_path = _ICONS_DIR / "navy" / "home.svg"
        if home_icon_path.exists():
            self.home_button.setIcon(QIcon(str(home_icon_path)))
        self.home_button.setObjectName("secondaryButton")
        self.home_button.setToolTip("لوحة التحكم")
        self.home_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.home_button.clicked.connect(lambda: self.sidebar.set_current_row(0))
        title_row.addWidget(self.home_button)

        self.page_title_label = QLabel()
        self.page_title_label.setObjectName("sectionTitle")
        title_row.addWidget(self.page_title_label)
        title_row.addStretch()
        content_layout.addLayout(title_row)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        # Plain leaf widget (no children) used to fade-reveal each page on
        # switch. A QGraphicsOpacityEffect must never be placed on the page
        # widgets themselves - they contain a Card with its own
        # QGraphicsDropShadowEffect, and nesting graphics effects breaks
        # rendering. Fading this overlay instead is visually equivalent and safe.
        self._transition_overlay = QWidget(self.stack)
        self._transition_overlay.setStyleSheet(f"background-color: {_TRANSITION_BG};")
        self._transition_overlay.hide()

        self._page_titles: list[str] = []
        self._page_icons: list[str] = []
        self._build_pages()

        dashboard = self.stack.widget(0)
        quick_access_items = [
            (title, icon, index)
            for index, (title, icon) in enumerate(zip(self._page_titles, self._page_icons))
            if index != 0
        ]
        dashboard.set_quick_access_items(quick_access_items)
        dashboard.navigate_requested.connect(self.sidebar.set_current_row)
        dashboard.logout_requested.connect(self.logout_requested)
        dashboard.open_invoice_statement_today.connect(self._open_invoice_statement_today)
        dashboard.open_installation_schedule_today.connect(self._open_installation_schedule_today)
        dashboard.open_attendance_today.connect(self._open_attendance_today)

        self.sidebar.current_row_changed.connect(self._switch_page)
        self.sidebar.set_current_row(0)

    def _add_page(self, title: str, widget: QWidget, icon_file: str) -> None:
        self._page_titles.append(title)
        self._page_icons.append(icon_file)
        self.stack.addWidget(widget)
        icon_path = _ICONS_DIR / icon_file
        self.sidebar.add_item(title, str(icon_path) if icon_path.exists() else None)

    def _switch_page(self, index: int) -> None:
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        self.page_title_label.setText(self._page_titles[index])
        # The dashboard has its own quick-access tile carousel, so the
        # sidebar steps aside to give it the full width; every other page
        # keeps the sidebar for normal navigation.
        self.sidebar.setVisible(index != 0)

        overlay = self._transition_overlay
        overlay.setGeometry(self.stack.rect())
        overlay_effect = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(overlay_effect)
        overlay.show()
        overlay.raise_()

        animation = QPropertyAnimation(overlay_effect, b"opacity", overlay)
        animation.setDuration(200)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(overlay.hide)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _open_invoice_statement_today(self) -> None:
        self.sidebar.set_current_row(self.stack.indexOf(self.invoice_statement_screen))
        self.invoice_statement_screen.show_for_date(QDate.currentDate())

    def _open_installation_schedule_today(self) -> None:
        self.sidebar.set_current_row(self.stack.indexOf(self.installation_schedule_screen))
        self.installation_schedule_screen.show_for_date(QDate.currentDate())

    def _open_attendance_today(self) -> None:
        self.sidebar.set_current_row(self.stack.indexOf(self.attendance_screen))
        self.attendance_screen.show_for_date(QDate.currentDate())

    def _build_pages(self) -> None:
        self._add_page(
            "لوحة التحكم", DashboardScreen(self._conn, self._user, self), "layout-dashboard.svg"
        )
        self._add_page("فواتير", InvoicesScreen(self._conn, self._user, self), "receipt.svg")
        self._add_page(
            "المخزون", InventoryTabScreen(self._conn, self._user, self), "package.svg"
        )
        self.installation_schedule_screen = InstallationScheduleScreen(self._conn, self._user, self)
        self._add_page("جدولة التركيبات", self.installation_schedule_screen, "calendar-clock.svg")
        self.invoice_statement_screen = InvoiceStatementScreen(self._conn, self._user, self)
        self._add_page("كشوفات الفواتير", self.invoice_statement_screen, "list-checks.svg")
        self._add_page(
            "سندات الصرف", ExpenseFormScreen(self._conn, self._user, self), "banknote.svg"
        )
        self._add_page(
            "سندات القبض", ReceiptFormScreen(self._conn, self._user, self), "hand-coins.svg"
        )
        self._add_page(
            "كشف الحسابات",
            AccountsStatementScreen(self._conn, self._user, self),
            "landmark.svg",
        )
        self._add_page(
            "فواتير الشراء",
            PurchaseInvoiceFormScreen(self._conn, self._user, self),
            "shopping-cart.svg",
        )
        self._add_page(
            "الموظفون", EmployeeListScreen(self._conn, self._user, self), "users.svg"
        )
        self.attendance_screen = AttendanceScreen(self._conn, self._user, self)
        self._add_page("الحضور والانصراف", self.attendance_screen, "calendar-check.svg")
        self._add_page(
            "سحوبات الموظفين", WithdrawalScreen(self._conn, self._user, self), "wallet.svg"
        )
        self._add_page(
            "تقرير الرواتب",
            SalaryReportScreen(self._conn, self._user, self),
            "chart-column.svg",
        )
        self._add_page(
            "التقارير المالية",
            FinancialReportScreen(self._conn, self._user, self),
            "trending-up.svg",
        )
        self._add_page(
            "التقرير الضريبي", TaxReportScreen(self._conn, self._user, self), "percent.svg"
        )
        if self._user["is_admin"]:
            self._add_page(
                "الإعدادات", SettingsScreen(self._conn, self._user, self), "settings.svg"
            )
