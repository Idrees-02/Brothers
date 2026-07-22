"""Modern centered login screen with a fade-in entrance animation and a
single crisp logo above the shop name."""

import sqlite3

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import resources_dir
from app.services.auth_service import AuthenticationError, login
from app.ui.widgets.card import Card

_LOGO_PATH = resources_dir() / "icons" / "logo.png"


class LoginScreen(QWidget):
    login_succeeded = Signal(object)  # emits the authenticated user row

    def __init__(self, conn: sqlite3.Connection, shop_name: str = "الاخوين لبيع السجاد"):
        super().__init__()
        self._conn = conn
        self.setWindowTitle(f"{shop_name} - تسجيل الدخول")
        self.resize(980, 640)
        # Styled via QWidget#loginScreen in app_rtl.qss, not an inline
        # setStyleSheet() call - setting a stylesheet directly on a widget
        # that has children breaks the app-wide QSS cascade for its
        # descendants (e.g. QPushButton rules stop applying to buttons
        # inside it), a documented Qt stylesheet gotcha.
        self.setObjectName("loginScreen")

        outer = QVBoxLayout(self)
        outer.addStretch(1)

        center_row = QHBoxLayout()
        center_row.addStretch(1)

        card = Card()
        card.setFixedWidth(380)
        center_row.addWidget(card)
        center_row.addStretch(1)
        outer.addLayout(center_row)
        outer.addStretch(1)

        logo_row = QHBoxLayout()
        logo_row.addStretch(1)
        if _LOGO_PATH.exists():
            logo_label = QLabel()
            logo_pixmap = QPixmap(str(_LOGO_PATH)).scaledToHeight(
                108, Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(logo_pixmap)
            logo_row.addWidget(logo_label)
        logo_row.addStretch(1)
        card.body_layout.addLayout(logo_row)
        card.body_layout.addSpacing(6)

        title = QLabel(shop_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("loginTitle")
        card.body_layout.addWidget(title)

        subtitle = QLabel("تسجيل الدخول إلى نظام الإدارة")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setObjectName("sectionSubtitle")
        card.body_layout.addWidget(subtitle)
        card.body_layout.addSpacing(10)

        card.body_layout.addWidget(QLabel("اسم المستخدم"))
        self.username_input = QLineEdit()
        card.body_layout.addWidget(self.username_input)

        card.body_layout.addWidget(QLabel("كلمة المرور"))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._attempt_login)
        card.body_layout.addWidget(self.password_input)
        card.body_layout.addSpacing(6)

        login_button = QPushButton("دخول")
        login_button.clicked.connect(self._attempt_login)
        card.body_layout.addWidget(login_button)

        self.username_input.setFocus()

        # Fade the whole top-level window in via its native windowOpacity
        # property - NOT a QGraphicsOpacityEffect, which conflicts with the
        # card's own QGraphicsDropShadowEffect when nested (breaks rendering).
        self.setWindowOpacity(0.0)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(380)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

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
