"""Accounts statement screen (كشف الحسابات) - balance of every account
(الصندوق النقدي / البنك / المالك / ...) and the full transaction history
behind each one, so the owner can see exactly how much each account holds."""

import sqlite3

from PySide6.QtWidgets import (
    QAbstractItemView,
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
from app.repositories import accounts_repo, settings_repo
from app.ui.vouchers.voucher_print import build_report_html, data_table_fragment, show_print_dialog_html
from app.ui.widgets.card import Card

_KIND_LABEL = {"receipt": "سند قبض", "expense": "سند صرف"}


class AccountsStatementScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user
        self._account_ids: list[int] = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        card = Card()
        outer_layout.addWidget(card)
        layout = card.body_layout

        subtitle = QLabel("رصيد كل حساب - اختر حساباً لعرض كل حركاته")
        subtitle.setObjectName("sectionSubtitle")
        layout.addWidget(subtitle)

        add_account_row = QHBoxLayout()
        self.new_account_input = QLineEdit()
        self.new_account_input.setPlaceholderText("اسم الحساب الجديد")
        self.new_account_input.returnPressed.connect(self._add_account)
        add_account_row.addWidget(self.new_account_input)
        add_account_button = QPushButton("إضافة حساب")
        add_account_button.clicked.connect(self._add_account)
        add_account_row.addWidget(add_account_button)
        self.toggle_active_button = QPushButton("تعطيل الحساب المحدد")
        self.toggle_active_button.setObjectName("secondaryButton")
        self.toggle_active_button.setEnabled(False)
        self.toggle_active_button.clicked.connect(self._toggle_selected_active)
        add_account_row.addWidget(self.toggle_active_button)
        add_account_row.addStretch()
        print_button = QPushButton("طباعة كشف الحسابات")
        print_button.setObjectName("secondaryButton")
        print_button.clicked.connect(self._print_statement)
        add_account_row.addWidget(print_button)
        layout.addLayout(add_account_row)

        self.accounts_table = QTableWidget(0, 3)
        self.accounts_table.setHorizontalHeaderLabels(["الحساب", "الرصيد", "الحالة"])
        self.accounts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.accounts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.accounts_table.itemSelectionChanged.connect(self._show_transactions)
        layout.addWidget(self.accounts_table)

        layout.addWidget(QLabel("حركات الحساب"))
        self.transactions_table = QTableWidget(0, 4)
        self.transactions_table.setHorizontalHeaderLabels(["النوع", "الوصف", "المبلغ", "التاريخ"])
        self.transactions_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.transactions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.transactions_table)

        self._accounts: list[sqlite3.Row] = []
        self._selected_account_id: int | None = None
        self._refresh_accounts()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_accounts()

    def _add_account(self) -> None:
        name = self.new_account_input.text().strip()
        if not name:
            QMessageBox.warning(self, "تعذر الإضافة", "اسم الحساب مطلوب")
            return
        try:
            accounts_repo.create_account(self._conn, name)
        except Exception as exc:  # noqa: BLE001 - e.g. UNIQUE constraint on a duplicate name
            QMessageBox.warning(self, "تعذر الإضافة", "يوجد حساب بنفس الاسم بالفعل" if "UNIQUE" in str(exc) else str(exc))
            return
        self.new_account_input.clear()
        self._refresh_accounts()

    def _toggle_selected_active(self) -> None:
        row = self.accounts_table.currentRow()
        if row < 0 or row >= len(self._accounts):
            return
        account = self._accounts[row]
        accounts_repo.set_active(self._conn, account["id"], not account["is_active"])
        self._refresh_accounts()

    def _refresh_accounts(self) -> None:
        self._accounts = accounts_repo.list_accounts(self._conn, include_inactive=True)
        self._account_ids = [a["id"] for a in self._accounts]
        self.accounts_table.setRowCount(len(self._accounts))
        for i, account in enumerate(self._accounts):
            self.accounts_table.setItem(i, 0, QTableWidgetItem(account["name"]))
            balance = accounts_repo.account_balance_fils(self._conn, account["id"])
            self.accounts_table.setItem(i, 1, QTableWidgetItem(f"{fils_to_bhd_str(balance)} د.ب"))
            status = "مفعّل" if account["is_active"] else "معطّل"
            self.accounts_table.setItem(i, 2, QTableWidgetItem(status))
        self.transactions_table.setRowCount(0)
        self.toggle_active_button.setEnabled(False)

    def _show_transactions(self) -> None:
        selected_rows = self.accounts_table.selectionModel().selectedRows()
        if not selected_rows:
            self.toggle_active_button.setEnabled(False)
            self._selected_account_id = None
            return
        row = selected_rows[0].row()
        if row < 0 or row >= len(self._account_ids):
            return
        account = self._accounts[row]
        self.toggle_active_button.setEnabled(True)
        self.toggle_active_button.setText(
            "تعطيل الحساب المحدد" if account["is_active"] else "تفعيل الحساب المحدد"
        )
        account_id = self._account_ids[row]
        self._selected_account_id = account_id
        transactions = accounts_repo.account_transactions(self._conn, account_id)
        self.transactions_table.setRowCount(len(transactions))
        for i, txn in enumerate(transactions):
            self.transactions_table.setItem(i, 0, QTableWidgetItem(_KIND_LABEL.get(txn["kind"], txn["kind"])))
            self.transactions_table.setItem(i, 1, QTableWidgetItem(txn["description"]))
            sign = "+" if txn["kind"] == "receipt" else "-"
            self.transactions_table.setItem(
                i, 2, QTableWidgetItem(f"{sign}{fils_to_bhd_str(txn['amount_fils'])}")
            )
            self.transactions_table.setItem(i, 3, QTableWidgetItem(txn["txn_date"]))

    def _print_statement(self) -> None:
        accounts_fragment = data_table_fragment(
            ["الحساب", "الرصيد", "الحالة"],
            [
                [
                    account["name"],
                    f"{fils_to_bhd_str(accounts_repo.account_balance_fils(self._conn, account['id']))} د.ب",
                    "مفعّل" if account["is_active"] else "معطّل",
                ]
                for account in self._accounts
            ],
        )
        sections = [accounts_fragment]

        if self._selected_account_id is not None:
            account = accounts_repo.get_account(self._conn, self._selected_account_id)
            transactions = accounts_repo.account_transactions(self._conn, self._selected_account_id)
            sections.append(f"<h3>حركات حساب: {account['name']}</h3>")
            sections.append(
                data_table_fragment(
                    ["النوع", "الوصف", "المبلغ", "التاريخ"],
                    [
                        [
                            _KIND_LABEL.get(txn["kind"], txn["kind"]),
                            txn["description"],
                            f"{'+' if txn['kind'] == 'receipt' else '-'}{fils_to_bhd_str(txn['amount_fils'])}",
                            txn["txn_date"],
                        ]
                        for txn in transactions
                    ],
                )
            )

        shop_name = settings_repo.get_settings(self._conn)["shop_name_ar"]
        html = build_report_html(shop_name, "كشف الحسابات", sections)
        show_print_dialog_html(self, html)
