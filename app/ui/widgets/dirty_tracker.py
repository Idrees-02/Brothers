"""Tracks whether a form has unsaved edits, and gates any "discard current
edits and navigate away" action (previous/next/jump-to-number, switching to
a new blank record) behind a confirmation dialog."""

from PySide6.QtCore import QObject
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLineEdit,
    QMessageBox,
    QWidget,
)


class DirtyTracker(QObject):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent = parent
        self._dirty = False
        self._suspended = False

    def watch(self, *widgets) -> None:
        """Connects each widget's own "value changed" signal to mark_dirty -
        covers every input type used across the invoice/voucher forms."""
        for widget in widgets:
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.mark_dirty)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self.mark_dirty)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self.mark_dirty)
            elif isinstance(widget, QDateEdit):
                widget.dateChanged.connect(self.mark_dirty)
            elif isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(self.mark_dirty)
            elif hasattr(widget, "items_changed"):  # LineItemsTable
                widget.items_changed.connect(self.mark_dirty)
            else:
                raise TypeError(f"DirtyTracker doesn't know how to watch {type(widget)!r}")

    def mark_dirty(self, *_args) -> None:
        if not self._suspended:
            self._dirty = True

    def mark_clean(self) -> None:
        self._dirty = False

    def is_dirty(self) -> bool:
        return self._dirty

    def set_fields_silently(self, apply_fn) -> None:
        """Runs apply_fn() (a block of self.xxx_input.setText(...)/setValue(...)
        calls that loads a record into the form) without those changes
        themselves flipping the dirty flag - only the user's own edits
        afterward should count as unsaved changes."""
        self._suspended = True
        try:
            apply_fn()
        finally:
            self._suspended = False
        self._dirty = False

    def confirm_discard(self) -> bool:
        """True if it's fine to proceed (nothing unsaved, or the user
        confirmed discarding it) - False means the caller should abort the
        navigation/reset that triggered this check."""
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self._parent,
            "تجاهل التغييرات؟",
            "البيانات المدخلة لم يتم حفظها وسيتم حذفها. هل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
