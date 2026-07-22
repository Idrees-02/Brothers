"""Stock-in voucher screen (سند إدخال) - adds quantity of an inventory item.
Supports browsing existing vouchers (previous/next, or jump to a voucher
number) and printing. The quantity/item of a past voucher can't be edited in
place (it would silently double-adjust quantity_on_hand) - only its note is
editable; to correct a quantity, void it conceptually by entering an
offsetting voucher instead."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDoubleSpinBox,
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

from app.repositories import items_repo, settings_repo, stock_repo
from app.services import inventory_service
from app.ui.vouchers.voucher_print import build_key_value_html, show_print_dialog_html
from app.ui.widgets.card import Card
from app.ui.widgets.dirty_tracker import DirtyTracker
from app.ui.widgets.item_combo import ItemCombo
from app.ui.widgets.override_dialog import prompt_override_password
from app.ui.widgets.record_navigator import RecordNavigator


class StockInFormScreen(QWidget):
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

        subtitle = QLabel("تسجيل سند إدخال جديد (إضافة كمية للمخزون)")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        self.navigator = RecordNavigator(number_label="رقم السند")
        self.navigator.previous_clicked.connect(self._go_previous)
        self.navigator.next_clicked.connect(self._go_next)
        self.navigator.jump_requested.connect(self._jump_to_number)
        self.navigator.print_clicked.connect(self._print_current)
        layout.addWidget(self.navigator)

        form = QFormLayout()
        self.item_combo = ItemCombo(conn)
        form.addRow("الصنف *", self.item_combo)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setDecimals(2)
        self.quantity_input.setMaximum(999_999)
        self.quantity_input.setMinimum(0.01)
        self.quantity_input.setValue(1)
        form.addRow("الكمية *", self.quantity_input)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        form.addRow("التاريخ", self.date_input)

        self.note_input = QLineEdit()
        form.addRow("ملاحظات", self.note_input)
        layout.addLayout(form)

        self._dirty_tracker = DirtyTracker(self)
        self._dirty_tracker.watch(self.item_combo, self.quantity_input, self.date_input, self.note_input)

        buttons_row = QHBoxLayout()
        self.save_button = QPushButton("حفظ سند الإدخال")
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

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["رقم السند", "الصنف", "الكمية", "التاريخ", "ملاحظات"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._open_selected_row)
        layout.addWidget(self.table)

        self._rows: list[sqlite3.Row] = []
        self._refresh_table()
        self._refresh_next_number_preview()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.item_combo.refresh()
        self._refresh_table()
        if self._browsed_id is None:
            self._refresh_next_number_preview()

    # ------------------------------------------------------------- saving
    def _save(self) -> None:
        self._do_save(then_print=False)

    def _save_and_print(self) -> None:
        self._do_save(then_print=True)

    def _do_save(self, then_print: bool) -> None:
        if self._browsed_id is None:
            item_id = self.item_combo.selected_item_id()
            if item_id is None:
                QMessageBox.warning(self, "تعذر الحفظ", "أضف صنفاً للمخزون أولاً")
                return
            try:
                new_id = inventory_service.record_stock_in(
                    self._conn,
                    self._user,
                    item_id=item_id,
                    quantity=self.quantity_input.value(),
                    movement_date=self.date_input.date().toString("yyyy-MM-dd"),
                    override_password_prompt=lambda: prompt_override_password("إنشاء سند إدخال", self),
                    note=self.note_input.text().strip() or None,
                )
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "تعذر الحفظ", str(exc))
                return
            self._last_created_id = new_id
            if then_print:
                self._print_voucher(new_id)
            self._reset_form()
            self._dirty_tracker.mark_clean()
            self._refresh_next_number_preview()
        else:
            try:
                inventory_service.update_movement_note(
                    self._conn,
                    self._user,
                    self._browsed_id,
                    override_password_prompt=lambda: prompt_override_password("تعديل سند إدخال", self),
                    note=self.note_input.text().strip() or None,
                )
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "تعذر الحفظ", str(exc))
                return
            if then_print:
                self._print_voucher(self._browsed_id)
            self._load_voucher(self._browsed_id)
        self._refresh_table()

    def _refresh_next_number_preview(self) -> None:
        next_no = settings_repo.preview_next_number(self._conn, "voucher", "stock_in")
        self.navigator.set_current_number(next_no)
        has_any = stock_repo.get_most_recent_movement_id(self._conn, "in") is not None
        self.navigator.set_navigation_enabled(has_any, False)
        self.navigator.set_print_enabled(self._last_created_id is not None)

    def _reset_form(self) -> None:
        self.quantity_input.setValue(1)
        self.note_input.clear()

    # -------------------------------------------------------- navigation
    def _load_voucher(self, movement_id: int) -> None:
        row = stock_repo.get_movement(self._conn, movement_id)
        if row is None:
            return
        self._browsed_id = movement_id
        item = items_repo.get_item(self._conn, row["item_id"])

        def apply():
            if item is not None:
                self.item_combo.set_item(item["id"])
            self.quantity_input.setValue(row["quantity"])
            self.date_input.setDate(QDate.fromString(row["movement_date"], "yyyy-MM-dd"))
            self.note_input.setText(row["note"] or "")

        self._dirty_tracker.set_fields_silently(apply)
        # Quantity/item of a past voucher can't be edited in place - only
        # the note is (see inventory_service.update_movement_note).
        self.item_combo.setEnabled(False)
        self.quantity_input.setEnabled(False)
        self.date_input.setEnabled(False)

        self.navigator.set_current_number(row["voucher_no"])
        self.navigator.set_print_enabled(True)
        self.navigator.set_navigation_enabled(
            stock_repo.get_adjacent_id(self._conn, movement_id, "previous") is not None,
            stock_repo.get_adjacent_id(self._conn, movement_id, "next") is not None,
        )
        self.save_button.setText("حفظ الملاحظات")
        self.new_voucher_button.setEnabled(True)

    def _start_new_voucher(self) -> None:
        if not self._dirty_tracker.confirm_discard():
            return
        self._browsed_id = None
        self.item_combo.setEnabled(True)
        self.quantity_input.setEnabled(True)
        self.date_input.setEnabled(True)
        self.save_button.setText("حفظ سند الإدخال")
        self.new_voucher_button.setEnabled(False)
        self._reset_form()
        self._dirty_tracker.mark_clean()
        self._refresh_next_number_preview()

    def _go_previous(self) -> None:
        if not self._dirty_tracker.confirm_discard():
            return
        if self._browsed_id is None:
            # Browsing from the blank "new voucher" preview - jump to the
            # most recently created voucher instead of doing nothing.
            most_recent = stock_repo.get_most_recent_movement_id(self._conn, "in")
            if most_recent is not None:
                self._load_voucher(most_recent)
            return
        adjacent = stock_repo.get_adjacent_id(self._conn, self._browsed_id, "previous")
        if adjacent is not None:
            self._load_voucher(adjacent)

    def _go_next(self) -> None:
        if self._browsed_id is None or not self._dirty_tracker.confirm_discard():
            return
        adjacent = stock_repo.get_adjacent_id(self._conn, self._browsed_id, "next")
        if adjacent is not None:
            self._load_voucher(adjacent)
        else:
            # Walked past the most recent voucher - back to the "new
            # voucher" preview state.
            self._browsed_id = None
            self.item_combo.setEnabled(True)
            self.quantity_input.setEnabled(True)
            self.date_input.setEnabled(True)
            self.save_button.setText("حفظ سند الإدخال")
            self.new_voucher_button.setEnabled(False)
            self._reset_form()
            self._dirty_tracker.mark_clean()
            self._refresh_next_number_preview()

    def _jump_to_number(self, voucher_no: str) -> None:
        if not voucher_no or not self._dirty_tracker.confirm_discard():
            return
        row = stock_repo.get_movement_by_voucher_no(self._conn, voucher_no)
        if row is None or row["movement_type"] != "in":
            QMessageBox.warning(self, "غير موجود", f"لا يوجد سند إدخال برقم {voucher_no}")
            return
        self._load_voucher(row["id"])

    def _open_selected_row(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows) or not self._dirty_tracker.confirm_discard():
            return
        self._load_voucher(self._rows[row]["id"])

    # ------------------------------------------------------------ table
    def _refresh_table(self) -> None:
        item_names = {i["id"]: i["name"] for i in items_repo.list_items(self._conn, include_inactive=True)}
        self._rows = stock_repo.list_movements(self._conn, movement_type="in", source="manual")
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["voucher_no"]))
            self.table.setItem(i, 1, QTableWidgetItem(item_names.get(row["item_id"], "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(row["quantity"])))
            self.table.setItem(i, 3, QTableWidgetItem(row["movement_date"]))
            self.table.setItem(i, 4, QTableWidgetItem(row["note"] or ""))

    # ------------------------------------------------------------ print
    def _print_voucher(self, movement_id: int) -> None:
        row = stock_repo.get_movement(self._conn, movement_id)
        if row is None:
            return
        item = items_repo.get_item(self._conn, row["item_id"])
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        html = build_key_value_html(
            shop_name,
            f"سند إدخال رقم {row['voucher_no']}",
            [
                ("رقم السند", row["voucher_no"]),
                ("الصنف", item["name"] if item else ""),
                ("الكمية", str(row["quantity"])),
                ("التاريخ", row["movement_date"]),
                ("ملاحظات", row["note"] or ""),
            ],
        )
        show_print_dialog_html(self, html)

    def _print_current(self) -> None:
        target_id = self._browsed_id or self._last_created_id
        if target_id is not None:
            self._print_voucher(target_id)
