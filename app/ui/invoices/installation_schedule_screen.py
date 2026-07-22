"""Installation scheduling screen (جدولة التركيبات) - pick a day, see every
installation invoice due that day, assign an installer, and mark each one
as installed / postponed / cancelled."""

import sqlite3

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.repositories import employees_repo, invoices_repo
from app.services import invoice_service
from app.ui.widgets.card import Card
from app.ui.widgets.money_spinbox import MoneySpinBox
from app.ui.widgets.override_dialog import prompt_override_password

_STATUS_LABEL = {
    "pending": "بانتظار التركيب",
    "installed": "تم التركيب",
    "postponed": "مؤجلة",
    "cancelled": "ملغاة",
}
_UNASSIGNED = "-- غير معين --"


def _kind_label(row) -> str:
    """This screen now lists both installation invoices and delivery-flagged
    cash invoices (see invoices_repo.list_installations_for_date) - they go
    through the exact same workflow, just labeled differently."""
    return "تركيب" if row["invoice_type"] == "installation" else "توصيل"


class InstallationOutcomeDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, invoice_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تم الإنجاز")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("اختر نتيجة التركيب:"))

        invoice = invoices_repo.get_invoice(conn, invoice_id)
        header = invoice["header"]
        paid = sum(p["amount_fils"] for p in invoice["payments"])
        self._remaining_fils = max(0, header["grand_total_fils"] - paid)

        self.installed_radio = QRadioButton("تم التركيب")
        self.installed_radio.setChecked(True)
        self.installed_radio.toggled.connect(self._toggle_payment_options)
        layout.addWidget(self.installed_radio)

        self.payment_options = QWidget()
        payment_layout = QFormLayout(self.payment_options)
        self.collected_amount_input = MoneySpinBox()
        self.collected_amount_input.set_fils_value(self._remaining_fils)
        payment_layout.addRow("المبلغ المستلم عند التركيب", self.collected_amount_input)
        self.payment_options.setVisible(self._remaining_fils > 0)
        layout.addWidget(self.payment_options)

        self.postponed_radio = QRadioButton("تم التأجيل")
        self.postponed_radio.toggled.connect(self._toggle_postpone_options)
        layout.addWidget(self.postponed_radio)

        self.postpone_options = QWidget()
        postpone_layout = QFormLayout(self.postpone_options)
        self.new_date_radio = QRadioButton("تحديد تاريخ جديد")
        self.new_date_radio.setChecked(True)
        postpone_layout.addRow(self.new_date_radio)
        self.new_date_input = QDateEdit(QDate.currentDate())
        self.new_date_input.setCalendarPopup(True)
        self.new_date_input.setDisplayFormat("yyyy-MM-dd")
        postpone_layout.addRow("التاريخ الجديد", self.new_date_input)
        self.no_date_radio = QRadioButton("تأجيل بدون تحديد تاريخ")
        postpone_layout.addRow(self.no_date_radio)
        self.postpone_options.setVisible(False)
        layout.addWidget(self.postpone_options)

        self.cancelled_radio = QRadioButton("تم الإلغاء")
        layout.addWidget(self.cancelled_radio)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_postpone_options(self, checked: bool) -> None:
        self.postpone_options.setVisible(checked)

    def _toggle_payment_options(self, checked: bool) -> None:
        self.payment_options.setVisible(checked and self._remaining_fils > 0)

    def result_data(self) -> dict:
        if self.installed_radio.isChecked():
            return {
                "action": "installed",
                "collected_amount_fils": self.collected_amount_input.fils_value(),
            }
        if self.postponed_radio.isChecked():
            if self.new_date_radio.isChecked():
                return {
                    "action": "postponed",
                    "new_date": self.new_date_input.date().toString("yyyy-MM-dd"),
                }
            return {"action": "postponed", "new_date": None}
        return {"action": "cancelled"}


class InstallationScheduleScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._row_invoice_ids: list[int] = []
        self._employee_ids: list[int] = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("اختر يوماً لعرض كل فواتير التركيب والتوصيل المستحقة فيه")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("اليوم:"))
        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        self.date_input.dateChanged.connect(self._refresh_table)
        date_row.addWidget(self.date_input)
        date_row.addStretch()
        layout.addLayout(date_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["رقم الفاتورة", "النوع", "الزبون", "الهاتف", "المنطقة", "الفني المسؤول", "الحالة"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self.action_button = QPushButton("تم الإنجاز")
        self.action_button.clicked.connect(self._mark_outcome)
        layout.addWidget(self.action_button)

        self._refresh_table()

    def show_for_date(self, target_date: QDate) -> None:
        """Entry point for the dashboard's "installations today" stat card."""
        self.date_input.setDate(target_date)
        self._refresh_table()

    def _employee_names(self) -> list[str]:
        employees = employees_repo.list_employees(self._conn)
        self._employee_ids = [e["id"] for e in employees]
        return [e["full_name"] for e in employees]

    def _refresh_table(self) -> None:
        work_date = self.date_input.date().toString("yyyy-MM-dd")
        rows = invoice_service.list_installations_for_date(self._conn, work_date)
        self._row_invoice_ids = [row["id"] for row in rows]
        employee_names = self._employee_names()

        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["invoice_no"]))
            self.table.setItem(i, 1, QTableWidgetItem(_kind_label(row)))
            self.table.setItem(i, 2, QTableWidgetItem(row["customer_name"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(row["phone"]))
            self.table.setItem(i, 4, QTableWidgetItem(row["area_region"] or ""))

            combo = QComboBox()
            combo.addItem(_UNASSIGNED)
            combo.addItems(employee_names)
            if row["assigned_employee_name"]:
                combo.setCurrentText(row["assigned_employee_name"])
            combo.currentIndexChanged.connect(
                lambda _index, invoice_id=row["id"], combo=combo: self._assign(invoice_id, combo)
            )
            self.table.setCellWidget(i, 5, combo)

            status_button = QPushButton(_STATUS_LABEL.get(row["installation_status"], ""))
            status_button.setObjectName("secondaryButton")
            status_button.setCursor(Qt.CursorShape.PointingHandCursor)
            status_button.clicked.connect(
                lambda _checked=False, invoice_id=row["id"]: self._mark_outcome_for_invoice(invoice_id)
            )
            self.table.setCellWidget(i, 6, status_button)

        # Rows sized purely from the plain-text columns above are too short
        # for the padded QComboBox in column 5 (its current selection - the
        # assigned technician's name - gets vertically clipped). Size rows
        # from actual cell-widget content instead.
        self.table.resizeRowsToContents()

    def _assign(self, invoice_id: int, combo: QComboBox) -> None:
        selected_text = combo.currentText()
        employee_id = None
        if selected_text != _UNASSIGNED:
            index = combo.currentIndex() - 1  # offset for the unassigned placeholder
            if 0 <= index < len(self._employee_ids):
                employee_id = self._employee_ids[index]
        try:
            invoice_service.assign_installer(
                self._conn,
                self._user,
                invoice_id,
                employee_id,
                override_password_prompt=lambda: prompt_override_password("تعيين فني التركيب", self),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر التعيين", str(exc))

    def _mark_outcome(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._row_invoice_ids):
            QMessageBox.information(self, "تنبيه", "الرجاء تحديد فاتورة من الجدول أولاً")
            return
        self._mark_outcome_for_invoice(self._row_invoice_ids[row])

    def _mark_outcome_for_invoice(self, invoice_id: int) -> None:
        dialog = InstallationOutcomeDialog(self._conn, invoice_id, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.result_data()

        try:
            if result["action"] == "installed":
                invoice_service.mark_installed(
                    self._conn, self._user, invoice_id,
                    override_password_prompt=lambda: prompt_override_password("تأكيد تم التركيب", self),
                )
                if result["collected_amount_fils"] > 0:
                    invoice_service.record_remaining_payment(
                        self._conn, self._user, invoice_id,
                        override_password_prompt=lambda: prompt_override_password(
                            "تحصيل المبلغ عند التركيب", self
                        ),
                        amount_fils=result["collected_amount_fils"],
                    )
            elif result["action"] == "postponed":
                invoice_service.postpone_installation(
                    self._conn, self._user, invoice_id,
                    override_password_prompt=lambda: prompt_override_password("تأجيل التركيب", self),
                    new_installation_date=result["new_date"],
                )
            else:
                invoice_service.cancel_installation(
                    self._conn, self._user, invoice_id,
                    override_password_prompt=lambda: prompt_override_password("إلغاء التركيب", self),
                )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر التحديث", str(exc))
            return
        self._refresh_table()
