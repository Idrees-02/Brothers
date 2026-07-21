"""BHD-aware money input: displays/edits 3-decimal BHD amounts, exposes the
underlying integer fils value so callers never handle float fils directly.
"""

from PySide6.QtWidgets import QDoubleSpinBox

from app.domain.money import FILS_PER_BHD, bhd_to_fils


class MoneySpinBox(QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(3)
        self.setMaximum(999_999.999)
        self.setMinimum(0.0)
        self.setSingleStep(0.5)
        self.setSuffix(" د.ب")

    def fils_value(self) -> int:
        return bhd_to_fils(self.value())

    def set_fils_value(self, fils: int) -> None:
        self.setValue(fils / FILS_PER_BHD)
