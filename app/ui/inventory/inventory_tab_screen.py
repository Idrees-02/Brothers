"""Combined "المخزون" entry: tab switcher between the inventory list, stock-in
vouchers (سند إدخال), and stock-out vouchers (سند إخراج)."""

import sqlite3

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.ui.inventory.inventory_screen import InventoryScreen
from app.ui.inventory.stock_in_form import StockInFormScreen
from app.ui.inventory.stock_out_form import StockOutFormScreen


class InventoryTabScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        layout.addWidget(tabs)
        tabs.addTab(InventoryScreen(conn, user, self), "الأصناف والكميات")
        tabs.addTab(StockInFormScreen(conn, user, self), "سند إدخال")
        tabs.addTab(StockOutFormScreen(conn, user, self), "سند إخراج")
