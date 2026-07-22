"""Modern dashboard / home screen: today's date header + at-a-glance stat
cards (today's invoices, today's installations due, employees present today).
"""

import sqlite3
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app.config import resources_dir
from app.repositories import employees_repo, invoices_repo
from app.ui.widgets.card import Card
from app.ui.widgets.quick_access_carousel import QuickAccessCarousel

_NAVY_ICONS_DIR = resources_dir() / "icons" / "navy"

_DAY_NAMES_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
_MONTH_NAMES_AR = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]


def _format_arabic_date(today: date) -> str:
    day_name = _DAY_NAMES_AR[today.weekday()]
    month_name = _MONTH_NAMES_AR[today.month - 1]
    return f"{day_name}، {today.day} {month_name} {today.year}"


class _StatCard(Card):
    clicked = Signal()

    def __init__(self, title: str, icon_file: str | None = None):
        super().__init__()
        self.setObjectName("dashboardStatCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        top_row = QHBoxLayout()
        if icon_file:
            icon_path = _NAVY_ICONS_DIR / icon_file
            if icon_path.exists():
                icon_label = QLabel()
                icon_label.setPixmap(
                    QPixmap(str(icon_path)).scaledToHeight(28)
                )
                top_row.addWidget(icon_label)
        top_row.addStretch()
        self.body_layout.addLayout(top_row)

        self.value_label = QLabel("0")
        self.value_label.setObjectName("dashboardStatValue")
        self.body_layout.addWidget(self.value_label)

        title_label = QLabel(title)
        title_label.setObjectName("sectionSubtitle")
        self.body_layout.addWidget(title_label)

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class DashboardScreen(QWidget):
    navigate_requested = Signal(int)
    logout_requested = Signal()
    open_invoice_statement_today = Signal()
    open_installation_schedule_today = Signal()
    open_attendance_today = Signal()

    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._carousel: QuickAccessCarousel | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)

        header_card = Card()
        # This card is small with no empty space for it to read as anything
        # but clutter, unlike the larger cards/tables elsewhere.
        header_card.set_watermark_enabled(False)
        self.date_label = QLabel()
        self.date_label.setObjectName("dashboardDateLabel")
        header_card.body_layout.addWidget(self.date_label)

        greeting_row = QHBoxLayout()
        self.greeting_label = QLabel(f"مرحباً، {user['display_name']}")
        self.greeting_label.setObjectName("sectionSubtitle")
        greeting_row.addWidget(self.greeting_label)
        greeting_row.addStretch()

        logout_button = QPushButton("تسجيل الخروج")
        logout_icon_path = _NAVY_ICONS_DIR / "log-out.svg"
        if logout_icon_path.exists():
            logout_button.setIcon(QIcon(str(logout_icon_path)))
        logout_button.setObjectName("secondaryButton")
        logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_button.clicked.connect(self._confirm_logout)
        greeting_row.addWidget(logout_button)
        header_card.body_layout.addLayout(greeting_row)

        self._layout.addWidget(header_card)
        self._layout.addSpacing(20)  # breathing room below the header, above the stat cards

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        self.invoices_today_card = _StatCard("عدد فواتير اليوم", "receipt.svg")
        self.invoices_today_card.clicked.connect(self.open_invoice_statement_today)
        self.installations_today_card = _StatCard("فواتير التركيب اليوم", "ruler.svg")
        self.installations_today_card.clicked.connect(self.open_installation_schedule_today)
        self.present_today_card = _StatCard("الموظفون الحاضرون اليوم", "calendar-check.svg")
        self.present_today_card.clicked.connect(self.open_attendance_today)
        cards_row.addWidget(self.invoices_today_card)
        cards_row.addWidget(self.installations_today_card)
        cards_row.addWidget(self.present_today_card)
        self._layout.addLayout(cards_row)
        self._layout.addStretch(1)

        # Zero-height marker sitting exactly between the stat-card row and the
        # quick-access row - MainWindow centers the big background watermark
        # on this widget's geometry (instead of the whole content area) so the
        # logo always lands fully visible in this gap instead of being
        # partially hidden behind whichever row happens to be taller.
        self._watermark_anchor = QWidget()
        self._watermark_anchor.setFixedHeight(0)
        self._layout.addWidget(self._watermark_anchor)
        self._layout.addStretch(1)

        self._quick_access_label = QLabel("الوصول السريع")
        self._quick_access_label.setObjectName("sectionSubtitle")
        self._quick_access_label.hide()
        self._layout.addWidget(self._quick_access_label)

        self._carousel_slot = QVBoxLayout()
        self._layout.addLayout(self._carousel_slot)
        self._layout.addStretch(1)

        self.refresh()

    def watermark_anchor(self) -> QWidget:
        """Widget MainWindow centers the shared background watermark on when
        this page is active - see the comment above `_watermark_anchor`."""
        return self._watermark_anchor

    def _confirm_logout(self) -> None:
        answer = QMessageBox.question(
            self,
            "تسجيل الخروج",
            "هل تريد تسجيل الخروج؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.logout_requested.emit()

    def set_quick_access_items(self, items: list[tuple[str, str, int]]) -> None:
        """items: (title, icon_file, page_index) for every other page."""
        if self._carousel is not None:
            self._carousel.setParent(None)
            self._carousel.deleteLater()
        self._carousel = QuickAccessCarousel(items)
        self._carousel.tile_clicked.connect(self.navigate_requested)
        self._carousel_slot.addWidget(self._carousel)
        self._quick_access_label.show()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def refresh(self) -> None:
        today = date.today()
        today_str = today.isoformat()
        self.date_label.setText(_format_arabic_date(today))
        self.invoices_today_card.set_value(
            invoices_repo.count_invoices_created_on(self._conn, today_str)
        )
        self.installations_today_card.set_value(
            invoices_repo.count_installations_for_date(self._conn, today_str)
        )
        self.present_today_card.set_value(
            employees_repo.count_present_on_date(self._conn, today_str)
        )
