"""QApplication setup: RTL layout, bundled Arabic font, base stylesheet."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.config import resources_dir


def build_application() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    family = _load_bundled_font()
    if family:
        app.setFont(QFont(family, 10))

    qss_path = resources_dir() / "qss" / "app_rtl.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    return app


def _load_bundled_font() -> str | None:
    font_path = resources_dir() / "fonts" / "Cairo-Variable.ttf"
    if not font_path.exists():
        return None
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else None
