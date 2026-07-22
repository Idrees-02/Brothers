"""Layout helper for compact, multi-field-per-row forms (used by the cash
and installation invoice forms) instead of QFormLayout's one-field-per-row,
which makes a form with many fields far taller than it needs to be."""

from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


def labeled_field(label_text: str, widget: QWidget) -> QVBoxLayout:
    """A field with its caption stacked above it."""
    column = QVBoxLayout()
    column.setSpacing(4)
    label = QLabel(label_text)
    label.setObjectName("sectionSubtitle")
    column.addWidget(label)
    column.addWidget(widget)
    return column


def expand_width(widget: QWidget) -> QWidget:
    """Lets a combo/spin/date box grow to fill its column instead of sizing
    to its content - used for rows built with equal stretch factors
    (addLayout(..., 1) per field) so the fields spread edge-to-edge across
    the row instead of bunching together with dead space at one end."""
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
    widget.setSizePolicy(policy)
    return widget
