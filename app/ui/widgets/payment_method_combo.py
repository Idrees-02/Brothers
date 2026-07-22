"""Dropdown for selecting an invoice's payment method (cash / بنفت باي /
ماستركارد / شيك) - a required choice on every invoice."""

from PySide6.QtWidgets import QComboBox

from app.services.invoice_service import PAYMENT_METHOD_LABELS_AR, PAYMENT_METHODS


class PaymentMethodCombo(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        for method in PAYMENT_METHODS:
            self.addItem(PAYMENT_METHOD_LABELS_AR[method], method)

    def selected_method(self) -> str:
        return self.currentData()

    def set_method(self, method: str) -> None:
        index = self.findData(method)
        if index >= 0:
            self.setCurrentIndex(index)
