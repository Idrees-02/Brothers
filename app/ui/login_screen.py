"""Login window shown at startup."""

import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.auth_service import AuthenticationError, login


class LoginScreen(QWidget):
    login_succeeded = Signal(object)  # emits the authenticated user row

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self._conn = conn
        self.setWindowTitle("الإخوة لبيع السجاد - تسجيل الدخول")
        self.setFixedSize(360, 260)

        layout = QVBoxLayout(self)
        title = QLabel("الإخوة لبيع السجاد")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        layout.addWidget(QLabel("اسم المستخدم"))
        self.username_input = QLineEdit()
        layout.addWidget(self.username_input)

        layout.addWidget(QLabel("كلمة المرور"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._attempt_login)
        layout.addWidget(self.password_input)

        login_button = QPushButton("دخول")
        login_button.clicked.connect(self._attempt_login)
        layout.addWidget(login_button)

        layout.addStretch()
        self.username_input.setFocus()

    def _attempt_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        try:
            user = login(self._conn, username, password)
        except AuthenticationError as exc:
            QMessageBox.warning(self, "خطأ في تسجيل الدخول", str(exc))
            self.password_input.clear()
            self.password_input.setFocus()
            return
        self.login_succeeded.emit(user)
