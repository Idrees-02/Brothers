"""Dropdown for selecting which account (الصندوق النقدي / البنك / المالك /
...) a voucher (سند صرف / سند قبض) affects."""

import sqlite3

from PySide6.QtWidgets import QComboBox

from app.repositories import accounts_repo


class AccountCombo(QComboBox):
    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.refresh()

    def refresh(self) -> None:
        current = self.selected_account_id()
        self.clear()
        for account in accounts_repo.list_accounts(self._conn):
            self.addItem(account["name"], account["id"])
        if current is not None:
            self.set_account(current)

    def selected_account_id(self) -> int | None:
        return self.currentData()

    def set_account(self, account_id: int) -> None:
        index = self.findData(account_id)
        if index >= 0:
            self.setCurrentIndex(index)
