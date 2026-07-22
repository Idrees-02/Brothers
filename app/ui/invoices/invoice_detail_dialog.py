"""Invoice detail dialog - view full details (including line items),
print/collect-remaining-payment/void/edit a single invoice. Used from both
the invoice statement screen (كشوفات الفواتير) and the installation
scheduling screen.
"""

import sqlite3

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.money import bhd_to_fils, fils_to_bhd_str
from app.repositories import invoices_repo, settings_repo
from app.services import invoice_service
from app.services.invoice_service import PAYMENT_METHOD_LABELS_AR
from app.ui.invoices.invoice_print import export_invoice_pdf, show_print_dialog
from app.ui.widgets.line_items_table import LineItemsTable
from app.ui.widgets.override_dialog import prompt_override_password
from app.ui.widgets.payment_method_combo import PaymentMethodCombo
from app.ui.widgets.record_navigator import RecordNavigator

_STATUS_LABEL = {"booked": "محجوزة", "completed": "مكتملة", "voided": "ملغاة"}
_TYPE_LABEL = {"cash": "قطع جاهزة", "installation": "تركيب وتفصيل"}


class InvoiceEditDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, invoice_id: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._invoice_id = invoice_id
        invoice = invoices_repo.get_invoice(conn, invoice_id)
        header = invoice["header"]
        self._is_installation = header["invoice_type"] == "installation"

        self.setWindowTitle(f"تعديل الفاتورة {header['invoice_no']}")
        self.resize(460, 520)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.customer_name_input = QLineEdit(header["customer_name"] or "")
        form.addRow("اسم الزبون" + (" *" if self._is_installation else ""), self.customer_name_input)

        self.phone_input = QLineEdit(header["phone"])
        form.addRow("رقم الهاتف *", self.phone_input)

        self.address_input = QLineEdit(header["address"] or "")
        self.area_region_input = QLineEdit(header["area_region"] or "")
        if self._is_installation:
            form.addRow("العنوان", self.address_input)
            form.addRow("المنطقة *", self.area_region_input)

        self.tax_included_checkbox = QCheckBox("المبلغ شامل الضريبة")
        self.tax_included_checkbox.setChecked(bool(header["tax_included"]))
        form.addRow(self.tax_included_checkbox)

        self.payment_method_combo = PaymentMethodCombo()
        self.payment_method_combo.set_method(header["payment_method"])
        form.addRow("طريقة الدفع *", self.payment_method_combo)
        layout.addLayout(form)

        layout.addWidget(QLabel("الأصناف"))
        self.items_table = LineItemsTable(
            quantity_label="المتر المربع" if self._is_installation else "الكمية", conn=conn
        )
        for item in invoice["items"]:
            self.items_table.add_row(
                item["description"], item["quantity"], item["unit_price_fils"] / 1000
            )
        layout.addWidget(self.items_table)

        buttons_row = QHBoxLayout()
        save_button = QPushButton("حفظ التعديلات")
        save_button.clicked.connect(self._save)
        buttons_row.addWidget(save_button)
        cancel_button = QPushButton("إلغاء")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_button)
        layout.addLayout(buttons_row)

    def _save(self) -> None:
        try:
            invoice_service.update_invoice(
                self._conn,
                self._user,
                self._invoice_id,
                phone=self.phone_input.text().strip(),
                items=self.items_table.items(),
                tax_included=self.tax_included_checkbox.isChecked(),
                override_password_prompt=lambda: prompt_override_password("تعديل فاتورة", self),
                customer_name=self.customer_name_input.text().strip() or None,
                address=self.address_input.text().strip() or None,
                area_region=self.area_region_input.text().strip() or None,
                payment_method=self.payment_method_combo.selected_method(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر حفظ التعديلات", str(exc))
            return
        self.accept()


class InvoiceDetailDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, invoice_id: int, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._invoice_id = invoice_id
        self.setWindowTitle("تفاصيل الفاتورة")
        self.resize(900, 720)
        self.setMinimumSize(820, 640)

        self.layout_ = QVBoxLayout(self)

        self.navigator = RecordNavigator(number_label="رقم الفاتورة")
        self.navigator.previous_clicked.connect(self._go_previous)
        self.navigator.next_clicked.connect(self._go_next)
        self.navigator.jump_requested.connect(self._jump_to_number)
        self.navigator.print_clicked.connect(self._print)
        self.layout_.addWidget(self.navigator)

        self.info_grid_container = QWidget()
        self.info_grid = QGridLayout(self.info_grid_container)
        self.info_grid.setHorizontalSpacing(24)
        self.info_grid.setVerticalSpacing(6)
        self.layout_.addWidget(self.info_grid_container)

        self.layout_.addWidget(QLabel("الأصناف"))
        self.items_table = QTableWidget(0, 4)
        self.items_table.setHorizontalHeaderLabels(["الوصف", "الكمية", "سعر الوحدة", "الإجمالي"])
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.layout_.addWidget(self.items_table)

        self.layout_.addWidget(QLabel("الدفعات"))
        self.payments_table = QTableWidget(0, 3)
        self.payments_table.setHorizontalHeaderLabels(["نوع الدفعة", "المبلغ", "التاريخ"])
        self.payments_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.payments_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.payments_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.layout_.addWidget(self.payments_table)

        buttons_row = QHBoxLayout()
        export_button = QPushButton("تصدير PDF")
        export_button.clicked.connect(self._export)
        buttons_row.addWidget(export_button)

        self.edit_button = QPushButton("تعديل")
        self.edit_button.setObjectName("secondaryButton")
        self.edit_button.clicked.connect(self._edit)
        buttons_row.addWidget(self.edit_button)

        self.collect_button = QPushButton("تحصيل المتبقي")
        self.collect_button.clicked.connect(self._collect_remaining)
        buttons_row.addWidget(self.collect_button)

        self.void_button = QPushButton("إلغاء الفاتورة")
        self.void_button.setObjectName("dangerButton")
        self.void_button.clicked.connect(self._void)
        buttons_row.addWidget(self.void_button)

        self.layout_.addLayout(buttons_row)
        self._refresh()

    @property
    def current_invoice_id(self) -> int:
        """Whatever invoice this dialog's own navigator has browsed to -
        callers that opened this dialog for one invoice_id should re-read
        this afterward instead of assuming it didn't move."""
        return self._invoice_id

    def _set_info_fields(self, pairs: list[tuple[str, str]]) -> None:
        """Repopulates the info grid as 2 side-by-side (label, value) columns
        instead of one long stacked column, so it reads compactly instead of
        eating a lot of vertical height."""
        while self.info_grid.count():
            item = self.info_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        columns = 2
        for index, (label_text, value_text) in enumerate(pairs):
            row, col = divmod(index, columns)
            label = QLabel(f"{label_text}:")
            label.setObjectName("sectionSubtitle")
            value = QLabel(value_text)
            value.setWordWrap(True)
            pair_col = col * 2
            self.info_grid.addWidget(label, row, pair_col)
            self.info_grid.addWidget(value, row, pair_col + 1)
        self.info_grid.setColumnStretch(1, 1)
        self.info_grid.setColumnStretch(3, 1)

    def _refresh(self) -> None:
        invoice = invoices_repo.get_invoice(self._conn, self._invoice_id)
        header = invoice["header"]
        paid = sum(p["amount_fils"] for p in invoice["payments"])
        remaining = header["grand_total_fils"] - paid

        self.navigator.set_current_number(header["invoice_no"])
        self.navigator.set_print_enabled(True)
        self.navigator.set_navigation_enabled(
            invoices_repo.get_adjacent_id(self._conn, self._invoice_id, "previous") is not None,
            invoices_repo.get_adjacent_id(self._conn, self._invoice_id, "next") is not None,
        )

        fields = [
            ("رقم الفاتورة", header["invoice_no"]),
            ("النوع", _TYPE_LABEL.get(header["invoice_type"], header["invoice_type"])),
            ("الزبون", header["customer_name"] or ""),
            ("الهاتف", header["phone"]),
            ("العنوان", header["address"] or ""),
            ("المنطقة", header["area_region"] or ""),
            ("الحالة", _STATUS_LABEL.get(header["status"], header["status"])),
            ("طريقة الدفع", PAYMENT_METHOD_LABELS_AR.get(header["payment_method"], "")),
        ]
        if header["invoice_type"] == "installation":
            fields.append(("تاريخ التركيب", header["installation_date"] or "غير محدد"))
        fields.append(("المجموع الفرعي", f"{fils_to_bhd_str(header['subtotal_fils'])} د.ب"))
        fields.append(
            (f"الضريبة ({header['tax_rate_percent']}%)", f"{fils_to_bhd_str(header['tax_amount_fils'])} د.ب")
        )
        fields.append(("الإجمالي", f"{fils_to_bhd_str(header['grand_total_fils'])} د.ب"))
        if header["deposit_fils"]:
            fields.append(("المقدم", f"{fils_to_bhd_str(header['deposit_fils'])} د.ب"))
        fields.append(("المدفوع", f"{fils_to_bhd_str(paid)} د.ب"))
        fields.append(("المتبقي", f"{fils_to_bhd_str(remaining)} د.ب"))
        self._set_info_fields(fields)

        self.items_table.setRowCount(len(invoice["items"]))
        for i, item in enumerate(invoice["items"]):
            self.items_table.setItem(i, 0, QTableWidgetItem(item["description"]))
            self.items_table.setItem(i, 1, QTableWidgetItem(str(item["quantity"])))
            self.items_table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(item["unit_price_fils"])))
            self.items_table.setItem(i, 3, QTableWidgetItem(fils_to_bhd_str(item["line_total_fils"])))

        self.payments_table.setRowCount(len(invoice["payments"]))
        for i, payment in enumerate(invoice["payments"]):
            self.payments_table.setItem(i, 0, QTableWidgetItem(payment["payment_type"]))
            self.payments_table.setItem(i, 1, QTableWidgetItem(fils_to_bhd_str(payment["amount_fils"])))
            self.payments_table.setItem(i, 2, QTableWidgetItem(payment["paid_at"]))

        self.collect_button.setEnabled(header["status"] == "booked" and remaining > 0)
        self.void_button.setEnabled(header["status"] != "voided")
        self.edit_button.setEnabled(header["status"] != "voided")

    def _go_previous(self) -> None:
        adjacent_id = invoices_repo.get_adjacent_id(self._conn, self._invoice_id, "previous")
        if adjacent_id is not None:
            self._invoice_id = adjacent_id
            self._refresh()

    def _go_next(self) -> None:
        adjacent_id = invoices_repo.get_adjacent_id(self._conn, self._invoice_id, "next")
        if adjacent_id is not None:
            self._invoice_id = adjacent_id
            self._refresh()

    def _jump_to_number(self, invoice_no: str) -> None:
        if not invoice_no:
            return
        invoice = invoices_repo.get_by_invoice_no(self._conn, invoice_no)
        if invoice is None:
            QMessageBox.warning(self, "غير موجود", f"لا توجد فاتورة برقم {invoice_no}")
            return
        self._invoice_id = invoice["id"]
        self._refresh()

    def _print(self) -> None:
        invoice = invoices_repo.get_invoice(self._conn, self._invoice_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        show_print_dialog(self, invoice, shop_name)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "تصدير PDF", "invoice.pdf", "PDF (*.pdf)")
        if not path:
            return
        invoice = invoices_repo.get_invoice(self._conn, self._invoice_id)
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        export_invoice_pdf(invoice, shop_name, path)

    def _edit(self) -> None:
        dialog = InvoiceEditDialog(self._conn, self._user, self._invoice_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh()

    def _collect_remaining(self) -> None:
        invoice = invoices_repo.get_invoice(self._conn, self._invoice_id)
        header = invoice["header"]
        paid = sum(p["amount_fils"] for p in invoice["payments"])
        remaining_fils = header["grand_total_fils"] - paid
        remaining_bhd = remaining_fils / 1000

        amount_bhd, ok = QInputDialog.getDouble(
            self,
            "تحصيل المتبقي",
            f"المبلغ المتبقي: {fils_to_bhd_str(remaining_fils)} د.ب\nأدخل المبلغ المراد تحصيله:",
            remaining_bhd,
            0.001,
            remaining_bhd,
            3,
        )
        if not ok:
            return

        try:
            invoice_service.record_remaining_payment(
                self._conn,
                self._user,
                self._invoice_id,
                override_password_prompt=lambda: prompt_override_password(
                    "تحصيل المبلغ المتبقي", self
                ),
                amount_fils=bhd_to_fils(amount_bhd),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر التحصيل", str(exc))
            return
        self._refresh()

    def _void(self) -> None:
        confirm = QMessageBox.question(
            self, "تأكيد الإلغاء", "هل أنت متأكد من إلغاء هذه الفاتورة؟"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            invoice_service.void_invoice(
                self._conn,
                self._user,
                self._invoice_id,
                override_password_prompt=lambda: prompt_override_password("إلغاء فاتورة", self),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الإلغاء", str(exc))
            return
        self._refresh()
