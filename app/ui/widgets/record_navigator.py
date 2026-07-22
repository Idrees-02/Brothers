"""Shared prev/next/search-by-number/print bar used by invoice and voucher
screens to browse existing records - "السند السابق"/"السند القادم" plus a
number field to jump straight to a record. Pure UI: the owning screen wires
these signals to its own repo lookups and knows how to load a record's
fields into its form."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget


class RecordNavigator(QWidget):
    previous_clicked = Signal()
    next_clicked = Signal()
    jump_requested = Signal(str)  # the typed number/invoice_no to jump to
    print_clicked = Signal()

    def __init__(self, number_label: str = "الرقم", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Same bidi-mirroring issue as the dashboard carousel arrows (see the
        # detailed comment in quick_access_carousel.py): Qt always renders
        # `‹`/`›` as their mirror image under the app's global RTL direction,
        # regardless of the widget's own layoutDirection. So each glyph below
        # is deliberately the opposite of the shape it should display.
        self.previous_button = QPushButton("› السابق")
        self.previous_button.setObjectName("secondaryButton")
        self.previous_button.clicked.connect(self.previous_clicked)
        layout.addWidget(self.previous_button)

        layout.addWidget(QLabel(number_label))
        self.number_input = QLineEdit()
        self.number_input.setPlaceholderText("ابحث بالرقم واضغط Enter")
        self.number_input.returnPressed.connect(
            lambda: self.jump_requested.emit(self.number_input.text().strip())
        )
        layout.addWidget(self.number_input)

        self.next_button = QPushButton("التالي ‹")
        self.next_button.setObjectName("secondaryButton")
        self.next_button.clicked.connect(self.next_clicked)
        layout.addWidget(self.next_button)

        self.print_button = QPushButton("طباعة")
        self.print_button.clicked.connect(self.print_clicked)
        self.print_button.setEnabled(False)
        layout.addWidget(self.print_button)

        layout.addStretch()

    def set_current_number(self, number: str | None) -> None:
        self.number_input.setText(number or "")

    def set_print_enabled(self, enabled: bool) -> None:
        self.print_button.setEnabled(enabled)

    def set_navigation_enabled(self, has_previous: bool, has_next: bool) -> None:
        self.previous_button.setEnabled(has_previous)
        self.next_button.setEnabled(has_next)
