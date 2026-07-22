"""Layout helper for compact, multi-field-per-row forms (used by the cash
and installation invoice forms) instead of QFormLayout's one-field-per-row,
which makes a form with many fields far taller than it needs to be."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def labeled_field(label_text: str, widget: QWidget) -> QVBoxLayout:
    """A field with its caption stacked above it."""
    column = QVBoxLayout()
    column.setSpacing(4)
    label = QLabel(label_text)
    label.setObjectName("sectionSubtitle")
    column.addWidget(label)
    column.addWidget(widget)
    return column
