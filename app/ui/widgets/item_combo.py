"""Dropdown for selecting an inventory item (used by the stock-in/stock-out
voucher forms)."""

import sqlite3

from PySide6.QtWidgets import QComboBox

from app.repositories import items_repo


class ItemCombo(QComboBox):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.refresh()

    def refresh(self) -> None:
        current = self.selected_item_id()
        self.clear()
        for item in items_repo.list_items(self._conn):
            self.addItem(item["name"], item["id"])
        if current is not None:
            self.set_item(current)

    def selected_item_id(self) -> int | None:
        return self.currentData()

    def set_item(self, item_id: int) -> None:
        index = self.findData(item_id)
        if index >= 0:
            self.setCurrentIndex(index)
