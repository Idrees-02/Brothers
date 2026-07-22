"""Stock-out voucher screen (سند إخراج) - removes quantity from the
inventory with a reason (تالف / إرجاع للمورد / تسوية جرد / استخدام داخلي /
أخرى). Supports browsing existing vouchers (previous/next, or jump to a
voucher number) and printing. The quantity/item of a past voucher can't be
edited in place (it would silently double-adjust quantity_on_hand) - only
its note/reason are editable."""

import sqlite3

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
from app.services.inventory_service import STOCK_OUT_REASONS, record_stock_out, update_movement_note
from app.ui.vouchers.voucher_print import build_key_value_html, show_print_dialog_html
from app.ui.widgets.card import Card
from app.ui.widgets.dirty_tracker import DirtyTracker
from app.ui.widgets.item_combo import ItemCombo
from app.ui.widgets.override_dialog import prompt_override_password
from app.ui.widgets.record_navigator import RecordNavigator

_OTHER_REASON = "أخرى"


class StockOutFormScreen(QWidget):
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

        subtitle = QLabel("تسجيل سند إخراج جديد (إنقاص كمية من المخزون)")
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

        self.reason_combo = QComboBox()
        for reason in STOCK_OUT_REASONS:
            self.reason_combo.addItem(reason)
        self.reason_combo.currentTextChanged.connect(self._on_reason_changed)
        form.addRow("السبب *", self.reason_combo)

        self.custom_reason_input = QLineEdit()
        self.custom_reason_input.setPlaceholderText("اكتب السبب")
        self.custom_reason_input.hide()
        form.addRow("سبب آخر", self.custom_reason_input)

        self.date_input = QDateEdit(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        form.addRow("التاريخ", self.date_input)

        self.note_input = QLineEdit()
        form.addRow("ملاحظات", self.note_input)
        layout.addLayout(form)

        self._dirty_tracker = DirtyTracker(self)
        self._dirty_tracker.watch(
            self.item_combo,
            self.quantity_input,
            self.reason_combo,
            self.custom_reason_input,
            self.date_input,
            self.note_input,
        )

        buttons_row = QHBoxLayout()
        self.save_button = QPushButton("حفظ سند الإخراج")
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

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["رقم السند", "الصنف", "الكمية", "السبب", "التاريخ", "ملاحظات"]
        )
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

    def _on_reason_changed(self, text: str) -> None:
        self.custom_reason_input.setVisible(text == _OTHER_REASON)

    def _selected_reason(self) -> str:
        if self.reason_combo.currentText() == _OTHER_REASON:
            return self.custom_reason_input.text().strip()
        return self.reason_combo.currentText()

    def _set_reason_display(self, reason: str) -> None:
        index = self.reason_combo.findText(reason)
        if index >= 0:
            self.reason_combo.setCurrentIndex(index)
            self.custom_reason_input.clear()
        else:
            self.reason_combo.setCurrentText(_OTHER_REASON)
            self.custom_reason_input.setText(reason)

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
                new_id = record_stock_out(
                    self._conn,
                    self._user,
                    item_id=item_id,
                    quantity=self.quantity_input.value(),
                    reason=self._selected_reason(),
                    movement_date=self.date_input.date().toString("yyyy-MM-dd"),
                    override_password_prompt=lambda: prompt_override_password("إنشاء سند إخراج", self),
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
                update_movement_note(
                    self._conn,
                    self._user,
                    self._browsed_id,
                    override_password_prompt=lambda: prompt_override_password("تعديل سند إخراج", self),
                    note=self.note_input.text().strip() or None,
                    reason=self._selected_reason(),
                )
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, "تعذر الحفظ", str(exc))
                return
            if then_print:
                self._print_voucher(self._browsed_id)
            self._load_voucher(self._browsed_id)
        self._refresh_table()

    def _refresh_next_number_preview(self) -> None:
        next_no = settings_repo.preview_next_number(self._conn, "voucher", "stock_out")
        self.navigator.set_current_number(next_no)
        has_any = stock_repo.get_most_recent_movement_id(self._conn, "out") is not None
        self.navigator.set_navigation_enabled(has_any, False)
        self.navigator.set_print_enabled(self._last_created_id is not None)

    def _reset_form(self) -> None:
        self.quantity_input.setValue(1)
        self.reason_combo.setCurrentIndex(0)
        self.custom_reason_input.clear()
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
            self._set_reason_display(row["reason"] or "")
            self.date_input.setDate(QDate.fromString(row["movement_date"], "yyyy-MM-dd"))
            self.note_input.setText(row["note"] or "")

        self._dirty_tracker.set_fields_silently(apply)
        # Quantity/item of a past voucher can't be edited in place - only
        # the reason/note are (see inventory_service.update_movement_note).
        self.item_combo.setEnabled(False)
        self.quantity_input.setEnabled(False)
        self.date_input.setEnabled(False)

        self.navigator.set_current_number(row["voucher_no"])
        self.navigator.set_print_enabled(True)
        self.navigator.set_navigation_enabled(
            stock_repo.get_adjacent_id(self._conn, movement_id, "previous") is not None,
            stock_repo.get_adjacent_id(self._conn, movement_id, "next") is not None,
        )
        self.save_button.setText("حفظ التعديلات")
        self.new_voucher_button.setEnabled(True)

    def _start_new_voucher(self) -> None:
        if not self._dirty_tracker.confirm_discard():
            return
        self._browsed_id = None
        self.item_combo.setEnabled(True)
        self.quantity_input.setEnabled(True)
        self.date_input.setEnabled(True)
        self.save_button.setText("حفظ سند الإخراج")
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
            most_recent = stock_repo.get_most_recent_movement_id(self._conn, "out")
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
            self.save_button.setText("حفظ سند الإخراج")
            self.new_voucher_button.setEnabled(False)
            self._reset_form()
            self._dirty_tracker.mark_clean()
            self._refresh_next_number_preview()

    def _jump_to_number(self, voucher_no: str) -> None:
        if not voucher_no or not self._dirty_tracker.confirm_discard():
            return
        row = stock_repo.get_movement_by_voucher_no(self._conn, voucher_no)
        if row is None or row["movement_type"] != "out":
            QMessageBox.warning(self, "غير موجود", f"لا يوجد سند إخراج برقم {voucher_no}")
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
        self._rows = stock_repo.list_movements(self._conn, movement_type="out", source="manual")
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["voucher_no"]))
            self.table.setItem(i, 1, QTableWidgetItem(item_names.get(row["item_id"], "")))
            self.table.setItem(i, 2, QTableWidgetItem(str(row["quantity"])))
            self.table.setItem(i, 3, QTableWidgetItem(row["reason"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(row["movement_date"]))
            self.table.setItem(i, 5, QTableWidgetItem(row["note"] or ""))

    # ------------------------------------------------------------ print
    def _print_voucher(self, movement_id: int) -> None:
        row = stock_repo.get_movement(self._conn, movement_id)
        if row is None:
            return
        item = items_repo.get_item(self._conn, row["item_id"])
        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        html = build_key_value_html(
            shop_name,
            f"سند إخراج رقم {row['voucher_no']}",
            [
                ("رقم السند", row["voucher_no"]),
                ("الصنف", item["name"] if item else ""),
                ("الكمية", str(row["quantity"])),
                ("السبب", row["reason"] or ""),
                ("التاريخ", row["movement_date"]),
                ("ملاحظات", row["note"] or ""),
            ],
        )
        show_print_dialog_html(self, html)

    def _print_current(self) -> None:
        target_id = self._browsed_id or self._last_created_id
        if target_id is not None:
            self._print_voucher(target_id)
