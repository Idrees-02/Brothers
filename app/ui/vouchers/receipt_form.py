"""Receipt vouchers screen (سندات قبض) - standalone records of money
received, mirroring the expense voucher screen. Supports browsing existing
vouchers (previous/next, or jump to a voucher number), editing a previously
saved one, a date-range filter over the list below, and printing a single
voucher or the currently-filtered list."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.money import fils_to_bhd_str
from app.repositories import accounts_repo, settings_repo, vouchers_repo
from app.services import voucher_service
from app.ui.vouchers.voucher_print import build_key_value_html, build_table_html, show_print_dialog_html
from app.ui.widgets.account_combo import AccountCombo
from app.ui.widgets.card import Card
from app.ui.widgets.date_range_picker import DateRangePicker
from app.ui.widgets.dirty_tracker import DirtyTracker
from app.ui.widgets.money_spinbox import MoneySpinBox
from app.ui.widgets.override_dialog import prompt_override_password
from app.ui.widgets.record_navigator import RecordNavigator


class ReceiptFormScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._browsed_id: int | None = None  # None = "new voucher" mode
        self._last_created_id: int | None = None

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("تسجيل سند قبض جديد (مبالغ مستلمة)")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        self.navigator = RecordNavigator(number_label="رقم السند")
        self.navigator.previous_clicked.connect(self._go_previous)
        self.navigator.next_clicked.connect(self._go_next)
        self.navigator.jump_requested.connect(self._jump_to_number)
        self.navigator.print_clicked.connect(self._print_current)
        layout.addWidget(self.navigator)

        form = QFormLayout()
        self.description_input = QLineEdit()
        form.addRow("الوصف *", self.description_input)

        self.amount_input = MoneySpinBox()
        form.addRow("المبلغ *", self.amount_input)

        self.account_combo = AccountCombo(conn)
        form.addRow("الحساب *", self.account_combo)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        form.addRow("التاريخ", self.date_input)

        self.note_input = QLineEdit()
        form.addRow("ملاحظات", self.note_input)
        layout.addLayout(form)

        self._dirty_tracker = DirtyTracker(self)
        self._dirty_tracker.watch(
            self.description_input, self.amount_input, self.account_combo, self.date_input, self.note_input
        )

        buttons_row = QHBoxLayout()
        self.save_button = QPushButton("حفظ سند القبض")
        self.save_button.clicked.connect(self._save)
        buttons_row.addWidget(self.save_button)

        self.save_print_button = QPushButton("حفظ وطباعة")
        self.save_print_button.clicked.connect(self._save_and_print)
        buttons_row.addWidget(self.save_print_button)

        self.new_voucher_button = QPushButton("سند جديد")
        self.new_voucher_button.setObjectName("secondaryButton")
        self.new_voucher_button.clicked.connect(self._start_new_voucher)
        self.new_voucher_button.setEnabled(False)
        buttons_row.addWidget(self.new_voucher_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        filter_row = QHBoxLayout()
        self.date_range = DateRangePicker()
        filter_row.addWidget(self.date_range)
        filter_button = QPushButton("تصفية")
        filter_button.clicked.connect(self._filter_by_date)
        filter_row.addWidget(filter_button)
        show_all_button = QPushButton("عرض الكل")
        show_all_button.setObjectName("secondaryButton")
        show_all_button.clicked.connect(self._refresh_table)
        filter_row.addWidget(show_all_button)
        print_list_button = QPushButton("طباعة القائمة")
        print_list_button.setObjectName("secondaryButton")
        print_list_button.clicked.connect(self._print_list)
        filter_row.addWidget(print_list_button)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["رقم السند", "الوصف", "المبلغ", "الحساب", "التاريخ"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._open_selected_row)
        layout.addWidget(self.table)

        self._filtered_rows: list[sqlite3.Row] = []
        self._refresh_table()

    # ------------------------------------------------------------- saving
    def _save(self) -> None:
        self._do_save(then_print=False)

    def _save_and_print(self) -> None:
        self._do_save(then_print=True)

    def _do_save(self, then_print: bool) -> None:
        account_id = self.account_combo.selected_account_id()
        if account_id is None:
            QMessageBox.warning(self, "تعذر الحفظ", "أضف حساباً أولاً")
            return
        try:
            if self._browsed_id is None:
                new_id = voucher_service.create_receipt(
                    self._conn,
                    self._user,
                    description=self.description_input.text().strip(),
                    amount_fils=self.amount_input.fils_value(),
                    receipt_date=self.date_input.date().toString("yyyy-MM-dd"),
                    account_id=account_id,
                    override_password_prompt=lambda: prompt_override_password("إنشاء سند قبض", self),
                    note=self.note_input.text().strip() or None,
                )
                self._last_created_id = new_id
            else:
                voucher_service.update_receipt(
                    self._conn,
                    self._user,
                    self._browsed_id,
                    description=self.description_input.text().strip(),
                    amount_fils=self.amount_input.fils_value(),
                    receipt_date=self.date_input.date().toString("yyyy-MM-dd"),
                    account_id=account_id,
                    override_password_prompt=lambda: prompt_override_password("تعديل سند قبض", self),
                    note=self.note_input.text().strip() or None,
                )
                new_id = self._browsed_id
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الحفظ", str(exc))
            return

        if then_print:
            self._print_voucher(new_id)

        if self._browsed_id is None:
            self._reset_form()
            self._dirty_tracker.mark_clean()
        else:
            self._load_voucher(new_id)
        self._refresh_table()

    def _reset_form(self) -> None:
        self.description_input.clear()
        self.amount_input.setValue(0)
        self.note_input.clear()

    # -------------------------------------------------------- navigation
    def _load_voucher(self, receipt_id: int) -> None:
        row = vouchers_repo.get_receipt(self._conn, receipt_id)
        if row is None:
            return
        self._browsed_id = receipt_id

        def apply():
            self.description_input.setText(row["description"])
            self.amount_input.set_fils_value(row["amount_fils"])
            if row["account_id"] is not None:
                self.account_combo.set_account(row["account_id"])
            self.date_input.setDate(QDate.fromString(row["receipt_date"], "yyyy-MM-dd"))
            self.note_input.setText(row["note"] or "")

        self._dirty_tracker.set_fields_silently(apply)

        self.navigator.set_current_number(row["voucher_no"])
        self.navigator.set_print_enabled(True)
        self.navigator.set_navigation_enabled(
            vouchers_repo.get_adjacent_receipt_id(self._conn, receipt_id, "previous") is not None,
            vouchers_repo.get_adjacent_receipt_id(self._conn, receipt_id, "next") is not None,
        )
        self.save_button.setText("حفظ التعديلات")
        self.new_voucher_button.setEnabled(True)

    def _start_new_voucher(self) -> None:
        if not self._dirty_tracker.confirm_discard():
            return
        self._browsed_id = None
        self.save_button.setText("حفظ سند القبض")
        self.new_voucher_button.setEnabled(False)
        self.navigator.set_current_number(None)
        self.navigator.set_navigation_enabled(False, False)
        self.navigator.set_print_enabled(self._last_created_id is not None)
        self._reset_form()
        self._dirty_tracker.mark_clean()

    def _go_previous(self) -> None:
        current = self._browsed_id
        if current is None or not self._dirty_tracker.confirm_discard():
            return
        adjacent = vouchers_repo.get_adjacent_receipt_id(self._conn, current, "previous")
        if adjacent is not None:
            self._load_voucher(adjacent)

    def _go_next(self) -> None:
        current = self._browsed_id
        if current is None or not self._dirty_tracker.confirm_discard():
            return
        adjacent = vouchers_repo.get_adjacent_receipt_id(self._conn, current, "next")
        if adjacent is not None:
            self._load_voucher(adjacent)

    def _jump_to_number(self, voucher_no: str) -> None:
        if not voucher_no or not self._dirty_tracker.confirm_discard():
            return
        row = vouchers_repo.get_receipt_by_voucher_no(self._conn, voucher_no)
        if row is None:
            QMessageBox.warning(self, "غير موجود", f"لا يوجد سند قبض برقم {voucher_no}")
            return
        self._load_voucher(row["id"])

    def _open_selected_row(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered_rows) or not self._dirty_tracker.confirm_discard():
            return
        self._load_voucher(self._filtered_rows[row]["id"])

    # ------------------------------------------------------------ table
    def _filter_by_date(self) -> None:
        start = self.date_range.start_date_str()
        end = self.date_range.end_date_str()
        self._populate(vouchers_repo.list_receipts(self._conn, start, end))

    def _refresh_table(self) -> None:
        self._populate(vouchers_repo.list_receipts(self._conn))

    def _populate(self, rows: list[sqlite3.Row]) -> None:
        self._filtered_rows = rows
        account_names = {a["id"]: a["name"] for a in accounts_repo.list_accounts(self._conn, include_inactive=True)}
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["voucher_no"]))
            self.table.setItem(i, 1, QTableWidgetItem(row["description"]))
            self.table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["amount_fils"])))
            self.table.setItem(i, 3, QTableWidgetItem(account_names.get(row["account_id"], "")))
            self.table.setItem(i, 4, QTableWidgetItem(row["receipt_date"]))

    # ------------------------------------------------------------ print
    def _print_voucher(self, receipt_id: int) -> None:
        row = vouchers_repo.get_receipt(self._conn, receipt_id)
        if row is None:
            return
        account_names = {a["id"]: a["name"] for a in accounts_repo.list_accounts(self._conn, include_inactive=True)}
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        html = build_key_value_html(
            shop_name,
            f"سند قبض رقم {row['voucher_no']}",
            [
                ("رقم السند", row["voucher_no"]),
                ("الوصف", row["description"]),
                ("المبلغ", f"{fils_to_bhd_str(row['amount_fils'])} د.ب"),
                ("الحساب", account_names.get(row["account_id"], "")),
                ("التاريخ", row["receipt_date"]),
                ("ملاحظات", row["note"] or ""),
            ],
        )
        show_print_dialog_html(self, html)

    def _print_current(self) -> None:
        target_id = self._browsed_id or self._last_created_id
        if target_id is not None:
            self._print_voucher(target_id)

    def _print_list(self) -> None:
        account_names = {a["id"]: a["name"] for a in accounts_repo.list_accounts(self._conn, include_inactive=True)}
        rows = [
            [
                row["voucher_no"],
                row["description"],
                fils_to_bhd_str(row["amount_fils"]),
                account_names.get(row["account_id"], ""),
                row["receipt_date"],
            ]
            for row in self._filtered_rows
        ]
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        html = build_table_html(
            shop_name,
            "كشف سندات القبض",
            ["رقم السند", "الوصف", "المبلغ", "الحساب", "التاريخ"],
            rows,
        )
        show_print_dialog_html(self, html)
