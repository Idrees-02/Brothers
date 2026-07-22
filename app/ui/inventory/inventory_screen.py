"""Inventory list (المخزون) - every item and its quantity on hand, plus
adding new items to track."""

import sqlite3

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
from app.repositories import items_repo
from app.services import inventory_service
from app.ui.widgets.card import Card
from app.ui.widgets.money_spinbox import MoneySpinBox
from app.ui.widgets.override_dialog import prompt_override_password

_UNIT_LABEL = {"piece": "قطعة", "sqm": "متر مربع"}


class InventoryScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._item_ids: list[int] = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("جميع الأصناف والكميات الموجودة في المخزون")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.name_input = QLineEdit()
        form.addRow("اسم الصنف *", self.name_input)

        self.unit_combo = QComboBox()
        self.unit_combo.addItem("قطعة", "piece")
        self.unit_combo.addItem("متر مربع", "sqm")
        form.addRow("الوحدة", self.unit_combo)

        self.unit_price_input = MoneySpinBox()
        form.addRow("سعر الوحدة", self.unit_price_input)
        layout.addLayout(form)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("إضافة صنف")
        add_button.clicked.connect(self._add_item)
        buttons_row.addWidget(add_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["اسم الصنف", "الوحدة", "سعر الوحدة", "الكمية المتوفرة"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self._refresh_table()

    def _add_item(self) -> None:
        try:
            inventory_service.create_item(
                self._conn,
                self._user,
                name=self.name_input.text().strip(),
                unit=self.unit_combo.currentData(),
                unit_price_fils=self.unit_price_input.fils_value(),
                override_password_prompt=lambda: prompt_override_password("إضافة صنف للمخزون", self),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الإضافة", str(exc))
            return
        self.name_input.clear()
        self.unit_price_input.setValue(0)
        self._refresh_table()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_table()

    def _refresh_table(self) -> None:
        rows = items_repo.list_items(self._conn, include_inactive=True)
        self._item_ids = [row["id"] for row in rows]
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["name"]))
            self.table.setItem(i, 1, QTableWidgetItem(_UNIT_LABEL.get(row["unit"], row["unit"])))
            self.table.setItem(i, 2, QTableWidgetItem(fils_to_bhd_str(row["unit_price_fils"])))
            self.table.setItem(i, 3, QTableWidgetItem(str(row["quantity_on_hand"])))
