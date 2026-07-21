"""One-time permission-override password prompt.

Used as the override_password_prompt callback passed into service-layer
calls: opens a modal asking for the override password, returns the entered
text or None if the user cancels. A correct entry only lets the single
action through - see app/services/permission_service.py.
"""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout


class OverridePasswordDialog(QDialog):
    def __init__(self, action_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تجاوز الصلاحية")
        self.setModal(True)

        layout = QVBoxLayout(self)
        message = QLabel(
            f"ليست لديك صلاحية لتنفيذ: {action_label}\nأدخل كلمة مرور التجاوز للسماح بهذا الإجراء مرة واحدة فقط."
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.password_input.setFocus()


def prompt_override_password(action_label: str, parent=None) -> str | None:
    """Convenience function matching the OverridePrompt signature expected
    by app/services/permission_service.require_permission."""
    dialog = OverridePasswordDialog(action_label, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.password_input.text()
    return None
