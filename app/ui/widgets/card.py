"""Reusable rounded white 'card' container with a soft drop shadow - the
base building block of the modern layout used across every screen."""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QScrollArea, QVBoxLayout


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(16, 30, 69, 35))  # navy at low opacity
        self.setGraphicsEffect(shadow)

        self.body_layout = QVBoxLayout(self)
        self.body_layout.setContentsMargins(20, 18, 20, 18)
        self.body_layout.setSpacing(12)

    def set_watermark_enabled(self, enabled: bool) -> None:
        """Opts this specific card out of the shared background watermark
        (e.g. small header cards where the logo has no room to read as
        anything but clutter) via a dynamic property + QSS attribute
        selector - see `QFrame#card[watermark="off"]` in app_rtl.qss."""
        self.setProperty("watermark", "on" if enabled else "off")
        self.style().unpolish(self)
        self.style().polish(self)


def scrollable(card: Card) -> QScrollArea:
    """Wraps a Card in a borderless, transparent QScrollArea so the whole
    page scrolls/grows with its content - e.g. an invoice's line-items table
    growing to fit every row - instead of squeezing everything into a fixed
    window height with a small internal scrollbar on just one widget.

    Styled via QScrollArea#transparentScrollArea in app_rtl.qss, NOT an
    inline setStyleSheet() call - setting a stylesheet directly on a widget
    that has children (the scroll area's viewport contains the whole Card
    subtree) breaks the app-wide QSS cascade for every descendant, making
    every QLineEdit/QPushButton/QTableWidget inside render unstyled
    (invisible borders/backgrounds). Same documented Qt stylesheet gotcha as
    login_screen.py's own comment about this."""
    scroll_area = QScrollArea()
    scroll_area.setObjectName("transparentScrollArea")
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setWidget(card)
    return scroll_area
