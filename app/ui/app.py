"""QApplication setup: RTL layout, bundled Arabic font, base stylesheet."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from app.config import resources_dir


def build_application() -> QApplication:
    app = QApplication.instance() or QApplication([])

    # Force the Fusion style instead of each platform's native widget theme.
    # Native styles (e.g. macOS Aqua) can fight with heavy custom QSS and
    # sometimes fail to paint a widget's styled background until a
    # hover/state-change event forces a repaint (buttons appearing
    # "invisible" until the mouse moves over them). Fusion renders purely
    # from the stylesheet, consistently across macOS/Windows/Linux.
    app.setStyle("Fusion")

    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

    family = _load_bundled_font()
    if family:
        # Cairo is a variable font; PySide6 can otherwise pick its thinnest
        # registered weight by default, which reads as faint/illegible dots
        # at small sizes (worst in table cell editors). Pin a legible weight
        # and a slightly larger base size explicitly.
        font = QFont(family, 11)
        font.setWeight(QFont.Weight.Medium)
        app.setFont(font)

    qss_path = resources_dir() / "qss" / "app_rtl.qss"
    if qss_path.exists():
        app.setStyleSheet(_render_qss(qss_path.read_text(encoding="utf-8")))

    icon_path = resources_dir() / "icons" / "app.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    return app


def _render_qss(qss_text: str) -> str:
    """Substitutes placeholders the QSS file can't hardcode itself - e.g. the
    card watermark's absolute file path, since Qt's `url()` in stylesheets
    needs a real filesystem path (forward slashes even on Windows), not one
    relative to the QSS file's own location."""
    watermark_path = resources_dir() / "icons" / "logo_watermark.png"
    watermark_css = ""
    if watermark_path.exists():
        watermark_css = (
            f"background-image: url({watermark_path.as_posix()});\n"
            "    background-repeat: no-repeat;\n"
            "    background-position: center;"
        )
    return qss_text.replace("{{CARD_WATERMARK_CSS}}", watermark_css)


def _load_bundled_font() -> str | None:
    font_path = resources_dir() / "fonts" / "Cairo-Variable.ttf"
    if not font_path.exists():
        return None
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else None
