"""Admin-only Settings screen: users/permissions, tax rate, override
password, default fees, working days, shop info."""

import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.repositories import settings_repo, users_repo
from app.services import settings_service
from app.ui.widgets.money_spinbox import MoneySpinBox
from app.ui.settings.user_form import UserFormDialog


class SettingsScreen(QWidget):
    def __init__(self, conn: sqlite3.Connection, user: sqlite3.Row, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._user = user

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._build_users_tab(), "المستخدمون")
        tabs.addTab(self._build_financial_tab(), "الإعدادات المالية")
        tabs.addTab(self._build_override_tab(), "كلمة مرور التجاوز")
        tabs.addTab(self._build_shop_tab(), "بيانات المحل")

    # ---------------------------------------------------------------- users
    def _build_users_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.users_table = QTableWidget(0, 4)
        self.users_table.setHorizontalHeaderLabels(["اسم المستخدم", "الاسم المعروض", "مدير", "نشط"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.users_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.users_table.doubleClicked.connect(self._edit_selected_user)
        layout.addWidget(self.users_table)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("إضافة مستخدم")
        add_button.clicked.connect(self._add_user)
        buttons_row.addWidget(add_button)

        edit_button = QPushButton("تعديل المحدد")
        edit_button.clicked.connect(self._edit_selected_user)
        buttons_row.addWidget(edit_button)

        deactivate_button = QPushButton("إيقاف تفعيل المحدد")
        deactivate_button.setObjectName("dangerButton")
        deactivate_button.clicked.connect(self._deactivate_selected_user)
        buttons_row.addWidget(deactivate_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        self._refresh_users_table()
        return tab

    def _refresh_users_table(self) -> None:
        rows = users_repo.list_users(self._conn, include_inactive=True)
        self._user_ids = [row["id"] for row in rows]
        self.users_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.users_table.setItem(i, 0, QTableWidgetItem(row["username"]))
            self.users_table.setItem(i, 1, QTableWidgetItem(row["display_name"]))
            self.users_table.setItem(i, 2, QTableWidgetItem("نعم" if row["is_admin"] else "لا"))
            self.users_table.setItem(i, 3, QTableWidgetItem("نعم" if row["is_active"] else "لا"))

    def _add_user(self) -> None:
        dialog = UserFormDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.result_data()
        try:
            settings_service.create_user_account(
                self._conn,
                self._user,
                username=data["username"],
                password=data["password"],
                display_name=data["display_name"],
                permissions=data["permissions"],
                is_admin=data["is_admin"],
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "تعذر الإضافة", str(exc))
            return
        self._refresh_users_table()

    def _edit_selected_user(self) -> None:
        row = self.users_table.currentRow()
        if row < 0 or row >= len(self._user_ids):
            return
        target_user = users_repo.get_user_by_id(self._conn, self._user_ids[row])
        dialog = UserFormDialog(existing_user=target_user, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.result_data()
        settings_service.update_user_account(
            self._conn,
            self._user,
            target_user["id"],
            display_name=data["display_name"],
            is_admin=data["is_admin"],
            permissions=data["permissions"],
        )
        if data["password"]:
            settings_service.reset_user_password(self._conn, self._user, target_user["id"], data["password"])
        self._refresh_users_table()

    def _deactivate_selected_user(self) -> None:
        row = self.users_table.currentRow()
        if row < 0 or row >= len(self._user_ids):
            return
        settings_service.deactivate_user(self._conn, self._user, self._user_ids[row])
        self._refresh_users_table()

    # ----------------------------------------------------------- financial
    def _build_financial_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        settings = settings_repo.get_settings(self._conn)

        self.tax_rate_input = QDoubleSpinBox()
        self.tax_rate_input.setSuffix(" %")
        self.tax_rate_input.setMaximum(100)
        self.tax_rate_input.setValue(settings["tax_rate_percent"])
        form.addRow("نسبة الضريبة", self.tax_rate_input)

        self.installation_fee_input = MoneySpinBox()
        self.installation_fee_input.set_fils_value(settings["default_installation_fee_fils"])
        form.addRow("رسوم التركيب الافتراضية", self.installation_fee_input)

        self.late_fine_input = MoneySpinBox()
        self.late_fine_input.set_fils_value(settings["late_fine_amount_fils"])
        form.addRow("غرامة التأخير لكل مرة", self.late_fine_input)

        self.working_days_input = QSpinBox()
        self.working_days_input.setRange(1, 31)
        self.working_days_input.setValue(settings["working_days_per_month"])
        form.addRow("أيام العمل في الشهر", self.working_days_input)

        layout.addLayout(form)

        save_button = QPushButton("حفظ الإعدادات المالية")
        save_button.clicked.connect(self._save_financial_settings)
        layout.addWidget(save_button)
        layout.addStretch()
        return tab

    def _save_financial_settings(self) -> None:
        settings_service.update_shop_settings(
            self._conn,
            self._user,
            tax_rate_percent=self.tax_rate_input.value(),
            default_installation_fee_fils=self.installation_fee_input.fils_value(),
            late_fine_amount_fils=self.late_fine_input.fils_value(),
            working_days_per_month=self.working_days_input.value(),
        )
        QMessageBox.information(self, "تم", "تم حفظ الإعدادات المالية")

    # ----------------------------------------------------------- override
    def _build_override_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        self.override_password_input = QLineEdit()
        self.override_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("كلمة مرور التجاوز الجديدة", self.override_password_input)
        layout.addLayout(form)

        save_button = QPushButton("حفظ كلمة مرور التجاوز")
        save_button.clicked.connect(self._save_override_password)
        layout.addWidget(save_button)
        layout.addStretch()
        return tab

    def _save_override_password(self) -> None:
        new_password = self.override_password_input.text()
        try:
            settings_service.update_override_password(self._conn, self._user, new_password)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "خطأ", str(exc))
            return
        self.override_password_input.clear()
        QMessageBox.information(self, "تم", "تم تحديث كلمة مرور التجاوز")

    # ---------------------------------------------------------------- shop
    def _build_shop_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()

        settings = settings_repo.get_settings(self._conn)

        self.shop_name_input = QLineEdit(settings["shop_name_ar"])
        form.addRow("اسم المحل", self.shop_name_input)

        self.shop_phone_input = QLineEdit(settings["shop_phone"] or "")
        form.addRow("هاتف المحل", self.shop_phone_input)

        self.shop_address_input = QLineEdit(settings["shop_address"] or "")
        form.addRow("عنوان المحل", self.shop_address_input)

        layout.addLayout(form)

        save_button = QPushButton("حفظ بيانات المحل")
        save_button.clicked.connect(self._save_shop_info)
        layout.addWidget(save_button)
        layout.addStretch()
        return tab

    def _save_shop_info(self) -> None:
        settings_service.update_shop_settings(
            self._conn,
            self._user,
            shop_name_ar=self.shop_name_input.text().strip(),
            shop_phone=self.shop_phone_input.text().strip() or None,
            shop_address=self.shop_address_input.text().strip() or None,
        )
        QMessageBox.information(self, "تم", "تم حفظ بيانات المحل")
