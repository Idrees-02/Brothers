"""Editable line-items table shared by cash invoices, installation invoices,
and purchase invoices - description/quantity/unit price with auto-computed
tax-amount and line-total columns.

Tax entry works in two directions, controlled by set_tax_included():
- tax NOT included (default): the user types the unit price (ex-tax); the
  tax amount and the tax-inclusive line total are computed automatically.
- tax included: the unit price becomes read-only and the line total becomes
  the input instead; the tax amount and ex-tax unit price are backed out of
  the entered total automatically.
In both modes the unit-price column always holds the ex-tax price, and
items() always returns ex-tax unit prices.
"""

import sqlite3

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.invoice_calc import line_total_fils, sum_line_items_fils
from app.domain.money import bhd_to_fils, fils_to_bhd_str, round_half_up_fils

_COL_DESCRIPTION, _COL_QUANTITY, _COL_UNIT_PRICE, _COL_TAX, _COL_LINE_TOTAL = range(5)


class LineItemsTable(QWidget):
    # Emitted whenever a row is added/removed or any total is recomputed -
    # screens embedding this table should connect to this (not to
    # self.items_table.table.itemChanged directly) to react to content
    # changes, since row construction blocks itemChanged internally.
    items_changed = Signal()

    def __init__(self, quantity_label: str = "الكمية", conn: sqlite3.Connection | None = None, parent=None):
        """conn: enables the F4 inventory picker (Qt.Key_F4 while focused on
        the table) - pass None to disable it for tables with no inventory
        link."""
        super().__init__(parent)
        self._conn = conn
        self._tax_rate_percent = 0.0
        self._tax_included = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["الوصف", quantity_label, "سعر الوحدة (د.ب)", "مبلغ الضريبة (د.ب)", "الإجمالي (د.ب)"]
        )
        self.table.itemChanged.connect(self._recompute_row_on_change)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # This table sizes itself to fit exactly its rows (see
        # _update_table_height) and never scrolls internally - the *page*
        # containing it is what scrolls when there are many items, instead
        # of squeezing every row into a small fixed-height box.
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if self._conn is not None:
            self.table.installEventFilter(self)
        layout.addWidget(self.table)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("إضافة صنف")
        add_button.clicked.connect(lambda: self.add_row())
        buttons_row.addWidget(add_button)

        remove_button = QPushButton("حذف الصنف المحدد")
        remove_button.clicked.connect(self._remove_selected_row)
        buttons_row.addWidget(remove_button)
        buttons_row.addStretch()

        if self._conn is not None:
            f4_hint = QLabel("F4 للبحث في المخزون")
            f4_hint.setObjectName("sectionSubtitle")
            buttons_row.addWidget(f4_hint)

        layout.addLayout(buttons_row)
        self._update_table_height()

    # ------------------------------------------------------------ tax mode
    def set_tax_rate(self, percent: float) -> None:
        if percent == self._tax_rate_percent:
            return
        self._tax_rate_percent = percent
        for row in range(self.table.rowCount()):
            self._recompute_row(row)

    def set_tax_included(self, included: bool) -> None:
        included = bool(included)
        if included == self._tax_included:
            return
        self._tax_included = included
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            self._apply_cell_editability(row)
        self.table.blockSignals(False)
        # Numbers themselves don't change on a mode switch - the unit-price
        # column already holds the ex-tax price - only which cell is the
        # input flips.

    def _apply_cell_editability(self, row: int) -> None:
        def set_editable(col: int, editable: bool) -> None:
            item = self.table.item(row, col)
            if item is None:
                return
            if editable:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        set_editable(_COL_UNIT_PRICE, not self._tax_included)
        set_editable(_COL_TAX, False)
        set_editable(_COL_LINE_TOTAL, self._tax_included)

    def eventFilter(self, obj, event) -> bool:
        if obj is self.table and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_F4:
            self._open_item_picker()
            return True
        return super().eventFilter(obj, event)

    def _open_item_picker(self) -> None:
        from app.ui.widgets.item_picker_dialog import ItemPickerDialog

        row = self.table.currentRow()
        if row < 0:
            self.add_row()
            row = self.table.rowCount() - 1

        dialog = ItemPickerDialog(self._conn, self)
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.selected_item is None:
            return

        item = dialog.selected_item
        self.table.blockSignals(True)
        self.table.item(row, _COL_DESCRIPTION).setText(item["name"])
        if self._tax_included:
            quantity = float(self.table.item(row, _COL_QUANTITY).text() or 1)
            total = line_total_fils(quantity, item["unit_price_fils"])
            self.table.item(row, _COL_LINE_TOTAL).setText(fils_to_bhd_str(total))
        else:
            self.table.item(row, _COL_UNIT_PRICE).setText(f"{item['unit_price_fils'] / 1000:.3f}")
        self.table.blockSignals(False)
        self._recompute_row(row)

    def add_row(self, description: str = "", quantity: float = 1, unit_price_bhd: float = 0.0) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        # Block signals while the row's cells are being populated - itemChanged
        # fires per setItem() call, and _recompute_row needs all cells to
        # exist before it can safely read/write them.
        self.table.blockSignals(True)
        self.table.setItem(row, _COL_DESCRIPTION, QTableWidgetItem(description))
        self.table.setItem(row, _COL_QUANTITY, QTableWidgetItem(str(quantity)))
        self.table.setItem(row, _COL_UNIT_PRICE, QTableWidgetItem(f"{unit_price_bhd:.3f}"))
        self.table.setItem(row, _COL_TAX, QTableWidgetItem("0.000"))
        total_item = QTableWidgetItem("0.000")
        if self._tax_included:
            # unit_price_bhd is tax-inclusive in this mode (e.g. a previously
            # saved tax-included invoice being loaded back) - seed the total
            # from it, then let the recompute back out unit price and tax.
            total_item.setText(fils_to_bhd_str(line_total_fils(quantity, bhd_to_fils(str(unit_price_bhd)))))
        self.table.setItem(row, _COL_LINE_TOTAL, total_item)
        self._apply_cell_editability(row)
        self.table.blockSignals(False)
        self._recompute_row(row)
        self._update_table_height()

    def _update_table_height(self) -> None:
        total = self.table.horizontalHeader().height() + 2 * self.table.frameWidth() + 4
        for row in range(self.table.rowCount()):
            total += self.table.rowHeight(row)
        self.table.setMinimumHeight(total)
        self.table.setMaximumHeight(total)

    def _remove_selected_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._update_table_height()
            self.items_changed.emit()

    def has_row_with_description(self, description: str) -> bool:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, _COL_DESCRIPTION)
            if item is not None and item.text() == description:
                return True
        return False

    def remove_row_by_description(self, description: str) -> bool:
        """Removes the first row whose description matches exactly - returns
        True if a row was removed. Used by toggles that auto-add a named row
        (e.g. a delivery fee line item) and need to auto-remove it again."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, _COL_DESCRIPTION)
            if item is not None and item.text() == description:
                self.table.removeRow(row)
                self._update_table_height()
                self.items_changed.emit()
                return True
        return False

    def _recompute_row_on_change(self, item: QTableWidgetItem) -> None:
        column = item.column()
        if column == _COL_QUANTITY:
            self._recompute_row(item.row())
        elif column == _COL_UNIT_PRICE and not self._tax_included:
            self._recompute_row(item.row())
        elif column == _COL_LINE_TOTAL and self._tax_included:
            self._recompute_row(item.row())

    def _recompute_row(self, row: int) -> None:
        if self._tax_included:
            self._recompute_from_total(row)
        else:
            self._recompute_from_price(row)

    def _recompute_from_price(self, row: int) -> None:
        try:
            quantity = float(self.table.item(row, _COL_QUANTITY).text() or 0)
            unit_price_fils = bhd_to_fils(self.table.item(row, _COL_UNIT_PRICE).text() or "0")
        except ValueError:
            return
        subtotal = line_total_fils(quantity, unit_price_fils)
        tax = self._tax_on_exclusive(subtotal)
        self.table.blockSignals(True)
        self.table.item(row, _COL_TAX).setText(fils_to_bhd_str(tax))
        self.table.item(row, _COL_LINE_TOTAL).setText(fils_to_bhd_str(subtotal + tax))
        self.table.blockSignals(False)
        self.items_changed.emit()

    def _recompute_from_total(self, row: int) -> None:
        try:
            quantity = float(self.table.item(row, _COL_QUANTITY).text() or 0)
            total_fils = bhd_to_fils(self.table.item(row, _COL_LINE_TOTAL).text() or "0")
        except ValueError:
            return
        tax = self._tax_in_inclusive(total_fils)
        exclusive = total_fils - tax
        unit_price_fils = round_half_up_fils(exclusive / quantity) if quantity else 0
        self.table.blockSignals(True)
        self.table.item(row, _COL_UNIT_PRICE).setText(fils_to_bhd_str(unit_price_fils))
        self.table.item(row, _COL_TAX).setText(fils_to_bhd_str(tax))
        self.table.blockSignals(False)
        self.items_changed.emit()

    def _tax_on_exclusive(self, subtotal_fils: int) -> int:
        if self._tax_rate_percent <= 0:
            return 0
        return round_half_up_fils(subtotal_fils * self._tax_rate_percent / 100)

    def _tax_in_inclusive(self, total_fils: int) -> int:
        if self._tax_rate_percent <= 0:
            return 0
        return round_half_up_fils(
            total_fils * self._tax_rate_percent / (100 + self._tax_rate_percent)
        )

    def items(self) -> list[dict]:
        result = []
        for row in range(self.table.rowCount()):
            description = (self.table.item(row, _COL_DESCRIPTION).text() or "").strip()
            if not description:
                continue
            quantity = float(self.table.item(row, _COL_QUANTITY).text() or 0)
            unit_price_fils = bhd_to_fils(self.table.item(row, _COL_UNIT_PRICE).text() or "0")
            result.append(
                {"description": description, "quantity": quantity, "unit_price_fils": unit_price_fils}
            )
        return result

    def subtotal_fils(self) -> int:
        return sum_line_items_fils(self.items())

    def clear_rows(self) -> None:
        self.table.setRowCount(0)
        self._update_table_height()
