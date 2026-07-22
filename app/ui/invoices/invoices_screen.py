"""Combined "فواتير" entry: a tab switcher between the cash/ready-made
invoice form and the installation/custom-fit invoice form, plus a shared bar
for browsing existing invoices (previous/next, or jump to an invoice
number) across both types. Opening this screen (or resetting to a blank
invoice) previews the next invoice number that will be assigned; browsing
to an existing invoice switches to whichever tab matches its type and loads
it into that tab's own form for inline viewing/editing."""

import sqlite3

from PySide6.QtWidgets import QMessageBox, QTabWidget, QVBoxLayout, QWidget

from app.repositories import invoices_repo, settings_repo
from app.ui.invoices.cash_invoice_form import CashInvoiceForm
from app.ui.invoices.installation_invoice_form import InstallationInvoiceForm
from app.ui.invoices.invoice_print import show_print_dialog
from app.ui.widgets.record_navigator import RecordNavigator

_CASH_TAB, _INSTALLATION_TAB = range(2)


class InvoicesScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._current_id: int | None = None  # None = previewing the next number, not browsing

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.navigator = RecordNavigator(number_label="رقم الفاتورة")
        self.navigator.previous_clicked.connect(self._go_previous)
        self.navigator.next_clicked.connect(self._go_next)
        self.navigator.jump_requested.connect(self._jump_to_number)
        self.navigator.print_clicked.connect(self._print_current)
        layout.addWidget(self.navigator)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.cash_form = CashInvoiceForm(conn, user, self)
        self.installation_form = InstallationInvoiceForm(conn, user, self)
        self.tabs.addTab(self.cash_form, "قطع جاهزة")
        self.tabs.addTab(self.installation_form, "تركيب وتفصيل")
        self.cash_form.invoice_saved.connect(self._on_invoice_saved)
        self.installation_form.invoice_saved.connect(self._on_invoice_saved)

        self._refresh_next_number_preview()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._current_id is None:
            self._refresh_next_number_preview()

    def _active_form(self):
        return self.cash_form if self.tabs.currentIndex() == _CASH_TAB else self.installation_form

    def _on_invoice_saved(self, invoice_id: int) -> None:
        header = invoices_repo.get_invoice(self._conn, invoice_id)["header"]
        self._current_id = invoice_id
        self._refresh_navigator_for_current(header["invoice_no"])

    def _refresh_next_number_preview(self) -> None:
        next_no = settings_repo.preview_next_number(self._conn, "invoice", "cash")
        self.navigator.set_current_number(next_no)
        has_any = invoices_repo.list_all_invoices(self._conn) != []
        self.navigator.set_navigation_enabled(has_any, False)
        self.navigator.set_print_enabled(False)

    def _refresh_navigator_for_current(self, invoice_no: str) -> None:
        self.navigator.set_current_number(invoice_no)
        self.navigator.set_navigation_enabled(
            invoices_repo.get_adjacent_id(self._conn, self._current_id, "previous") is not None, True
        )
        self.navigator.set_print_enabled(True)

    def _load_invoice(self, invoice_id: int) -> None:
        header = invoices_repo.get_invoice(self._conn, invoice_id)["header"]
        self.tabs.setCurrentIndex(_CASH_TAB if header["invoice_type"] == "cash" else _INSTALLATION_TAB)
        self._active_form().load_invoice_for_edit(invoice_id)
        self._current_id = invoice_id
        self._refresh_navigator_for_current(header["invoice_no"])

    def _go_previous(self) -> None:
        if not self._active_form().confirm_discard():
            return
        if self._current_id is None:
            rows = invoices_repo.list_all_invoices(self._conn)
            if rows:
                self._load_invoice(rows[0]["id"])
            return
        adjacent = invoices_repo.get_adjacent_id(self._conn, self._current_id, "previous")
        if adjacent is not None:
            self._load_invoice(adjacent)

    def _go_next(self) -> None:
        if self._current_id is None or not self._active_form().confirm_discard():
            return
        adjacent = invoices_repo.get_adjacent_id(self._conn, self._current_id, "next")
        if adjacent is not None:
            self._load_invoice(adjacent)
        else:
            # Walked past the most recent invoice - back to the "new invoice"
            # preview state (the active form itself already confirmed above).
            self._current_id = None
            self._active_form().start_new()
            self._refresh_next_number_preview()

    def _jump_to_number(self, invoice_no: str) -> None:
        if not invoice_no or not self._active_form().confirm_discard():
            return
        invoice = invoices_repo.get_by_invoice_no(self._conn, invoice_no)
        if invoice is None:
            QMessageBox.warning(self, "غير موجود", f"لا توجد فاتورة برقم {invoice_no}")
            return
        self._load_invoice(invoice["id"])

    def _print_current(self) -> None:
        if self._current_id is None:
            return
        invoice = invoices_repo.get_invoice(self._conn, self._current_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        show_print_dialog(self, invoice, shop_name)
