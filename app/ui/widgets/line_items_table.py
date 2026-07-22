"""Editable line-items table shared by cash invoices, installation invoices,
and purchase invoices - description/quantity/unit price with an
auto-computed line total column.
"""

import sqlite3

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.domain.invoice_calc import line_total_fils, sum_line_items_fils
from app.domain.money import bhd_to_fils, fils_to_bhd_str

_COL_DESCRIPTION, _COL_QUANTITY, _COL_UNIT_PRICE, _COL_LINE_TOTAL = range(4)


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["الوصف", quantity_label, "سعر الوحدة (د.ب)", "الإجمالي (د.ب)"]
        )
        self.table.itemChanged.connect(self._recompute_row_on_change)
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
        self.table.item(row, _COL_UNIT_PRICE).setText(f"{item['unit_price_fils'] / 1000:.3f}")
        self.table.blockSignals(False)
        self._recompute_row(row)

    def add_row(self, description: str = "", quantity: float = 1, unit_price_bhd: float = 0.0) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        # Block signals while the row's cells are being populated - itemChanged
        # fires per setItem() call, and _recompute_row needs all four cells
        # to exist before it can safely read/write them.
        self.table.blockSignals(True)
        self.table.setItem(row, _COL_DESCRIPTION, QTableWidgetItem(description))
        self.table.setItem(row, _COL_QUANTITY, QTableWidgetItem(str(quantity)))
        self.table.setItem(row, _COL_UNIT_PRICE, QTableWidgetItem(f"{unit_price_bhd:.3f}"))
        total_item = QTableWidgetItem("0.000")
        total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, _COL_LINE_TOTAL, total_item)
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

    def _recompute_row_on_change(self, item: QTableWidgetItem) -> None:
        if item.column() in (_COL_QUANTITY, _COL_UNIT_PRICE):
            self._recompute_row(item.row())

    def _recompute_row(self, row: int) -> None:
        try:
            quantity = float(self.table.item(row, _COL_QUANTITY).text() or 0)
            unit_price_fils = bhd_to_fils(self.table.item(row, _COL_UNIT_PRICE).text() or "0")
        except ValueError:
            return
        total = line_total_fils(quantity, unit_price_fils)
        self.table.blockSignals(True)
        self.table.item(row, _COL_LINE_TOTAL).setText(fils_to_bhd_str(total))
        self.table.blockSignals(False)
        self.items_changed.emit()

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
