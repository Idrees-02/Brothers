"""F4 inventory picker - searchable list of inventory items (with quantity on
hand) used to fill a line-item row's description/unit price instead of
typing them by hand."""

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.domain.money import fils_to_bhd_str
from app.repositories import items_repo

_UNIT_LABEL = {"piece": "قطعة", "sqm": "متر مربع"}


class ItemPickerDialog(QDialog):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._rows: list[sqlite3.Row] = []
        self.selected_item: sqlite3.Row | None = None

        self.setWindowTitle("اختيار صنف من المخزون")
        self.resize(560, 420)
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("ابحث باسم الصنف")
        self.search_input.textChanged.connect(self._filter)
        search_row.addWidget(self.search_input)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["اسم الصنف", "سعر الوحدة", "الكمية المتوفرة"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.doubleClicked.connect(self._accept_selected)
        layout.addWidget(self.table)

        hint = QLabel("انقر مرتين على الصنف أو اضغط Enter لاختياره")
        hint.setObjectName("sectionSubtitle")
        layout.addWidget(hint)

        buttons_row = QHBoxLayout()
        select_button = QPushButton("اختيار")
        select_button.clicked.connect(self._accept_selected)
        buttons_row.addWidget(select_button)
        cancel_button = QPushButton("إلغاء")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_button)
        layout.addLayout(buttons_row)

        self.search_input.setFocus()
        self._filter("")

    def _filter(self, query: str) -> None:
        query = query.strip()
        self._rows = (
            items_repo.search_items(self._conn, query) if query else items_repo.list_items(self._conn)
        )
        self.table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(fils_to_bhd_str(row["unit_price_fils"])))
            qty_item = QTableWidgetItem(f"{row['quantity_on_hand']:g} {_UNIT_LABEL.get(row['unit'], row['unit'])}")
            self.table.setItem(i, 2, qty_item)
        if self._rows:
            self.table.selectRow(0)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._accept_selected()
            return
        super().keyPressEvent(event)

    def _accept_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        self.selected_item = self._rows[row]
        self.accept()
