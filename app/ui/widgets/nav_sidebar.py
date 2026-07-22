"""Modern navy sidebar navigation: logo header, icon-labelled nav list with
a rounded accent-pill selection state, and a user badge footer."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import resources_dir


class NavSidebar(QWidget):
    current_row_changed = Signal(int)

    def __init__(self, shop_name: str, user_display_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("navSidebar")
        self.setFixedWidth(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo_path = resources_dir() / "icons" / "logo.png"
        if logo_path.exists():
            logo_label = QLabel()
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = QPixmap(str(logo_path)).scaledToHeight(
                84, Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(pixmap)
            logo_label.setContentsMargins(0, 22, 0, 6)
            layout.addWidget(logo_label)
        else:
            brand_label = QLabel(shop_name)
            brand_label.setObjectName("brandLabel")
            brand_label.setWordWrap(True)
            layout.addWidget(brand_label)

        subtitle_label = QLabel("شيدو للأنظمة")
        subtitle_label.setObjectName("brandSubLabel")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_label)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("navList")
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setIconSize(self.list_widget.iconSize() * 1.1)
        self.list_widget.currentRowChanged.connect(self.current_row_changed)
        self.list_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.list_widget, 1)

        self.user_badge = QLabel(user_display_name)
        self.user_badge.setObjectName("userBadge")
        layout.addWidget(self.user_badge)

    def add_item(self, text: str, icon_path: str | None = None) -> None:
        item = QListWidgetItem(text)
        if icon_path:
            item.setIcon(QIcon(icon_path))
        self.list_widget.addItem(item)

    def set_current_row(self, row: int) -> None:
        self.list_widget.setCurrentRow(row)

    def current_row(self) -> int:
        return self.list_widget.currentRow()
