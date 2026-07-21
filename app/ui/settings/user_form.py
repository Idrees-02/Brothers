"""Create/edit user account dialog with the five permission checkboxes."""

import sqlite3

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)


class UserFormDialog(QDialog):
    def __init__(self, existing_user: sqlite3.Row | None = None, parent=None):
        super().__init__(parent)
        self._editing = existing_user is not None
        self.setWindowTitle("تعديل مستخدم" if self._editing else "إضافة مستخدم")

        layout = QFormLayout(self)

        self.username_input = QLineEdit()
        if self._editing:
            self.username_input.setText(existing_user["username"])
            self.username_input.setEnabled(False)
        layout.addRow("اسم المستخدم *", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(
            "اتركه فارغاً لعدم التغيير" if self._editing else ""
        )
        layout.addRow("كلمة المرور" + (" *" if not self._editing else ""), self.password_input)

        self.display_name_input = QLineEdit()
        if self._editing:
            self.display_name_input.setText(existing_user["display_name"])
        layout.addRow("الاسم المعروض *", self.display_name_input)

        self.is_admin_checkbox = QCheckBox("مدير (صلاحيات كاملة)")
        if self._editing:
            self.is_admin_checkbox.setChecked(bool(existing_user["is_admin"]))
        layout.addRow(self.is_admin_checkbox)

        self.permission_checkboxes = {
            "can_create_invoice": QCheckBox("إنشاء الفواتير"),
            "can_edit_invoice": QCheckBox("تعديل الفواتير"),
            "can_view_only": QCheckBox("عرض فقط (بدون تعديل)"),
            "can_create_voucher": QCheckBox("إنشاء سندات الصرف"),
            "can_register_attendance": QCheckBox("تسجيل الحضور والانصراف"),
        }
        for key, checkbox in self.permission_checkboxes.items():
            if self._editing:
                checkbox.setChecked(bool(existing_user[key]))
            layout.addRow(checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def result_data(self) -> dict:
        return {
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
            "display_name": self.display_name_input.text().strip(),
            "is_admin": self.is_admin_checkbox.isChecked(),
            "permissions": {
                key: checkbox.isChecked() for key, checkbox in self.permission_checkboxes.items()
            },
        }
