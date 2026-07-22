"""Paginated strip of quick-access shortcut tiles (5 per group) with
previous/next controls - used on the Dashboard to replace the sidebar as
the primary way to jump to a section."""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import resources_dir

_GROUP_SIZE = 5
_ICON_SIZE = 44
_NAVY_ICONS_DIR = resources_dir() / "icons" / "navy"


def _load_crisp_pixmap(icon_path, size: int):
    """QPixmap(path).scaledToHeight(...) ignores devicePixelRatio, so on
    HiDPI/Retina screens the bitmap is upscaled from a too-low resolution and
    reads as faint/blurry. Rendering through QIcon at the physical pixel size
    (then tagging the resulting pixmap with that ratio) keeps icons crisp."""
    screen = QGuiApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen is not None else 1.0
    pixmap = QIcon(str(icon_path)).pixmap(QSize(int(size * dpr), int(size * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


class _Tile(QPushButton):
    def __init__(self, title: str, icon_file: str | None, page_index: int):
        super().__init__()
        self.page_index = page_index
        self.setObjectName("dashboardTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(140, 250)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(8)

        # Icon + label form one centered block (stretch on both sides)
        # instead of the icon pinned to the top and the label pinned to the
        # bottom of the tile.
        layout.addStretch()

        if icon_file:
            icon_path = _NAVY_ICONS_DIR / icon_file
            if icon_path.exists():
                icon_label = QLabel()
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setPixmap(_load_crisp_pixmap(icon_path, _ICON_SIZE))
                layout.addWidget(icon_label)
                layout.addSpacing(8)

        text_label = QLabel(title)
        text_label.setObjectName("dashboardTileLabel")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

        layout.addStretch()


class QuickAccessCarousel(QWidget):
    tile_clicked = Signal(int)  # emits the target page index

    def __init__(self, items: list[tuple[str, str, int]], parent=None):
        """items: list of (title, icon_file, page_index) in nav order."""
        super().__init__(parent)
        self._items = items
        self._current_group = 0
        self._fade_animation: QPropertyAnimation | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # `›`/`‹` (and even plain ASCII `<`/`>`) are Unicode bidi-mirrored
        # characters: under the app's global RightToLeft direction, Qt's text
        # shaper always renders them as their mirror image - this happens at
        # the app-direction level, not the individual widget's own
        # layoutDirection (setting that on the button has no effect on it).
        # So each glyph below is deliberately the *opposite* of what it looks
        # like in the source - `›` is assigned to make the button *display*
        # `‹`, and vice versa. This button sits on the visual right (first
        # widget added to an RTL-mirrored QHBoxLayout ends up rightmost) and
        # should display a right-pointing arrow (pointing away from the
        # tiles), hence assigning `‹` here.
        self.prev_button = QPushButton("‹")
        self.prev_button.setObjectName("carouselArrow")
        self.prev_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_button.clicked.connect(self._go_prev)
        layout.addWidget(self.prev_button)

        self._tiles_container = QWidget()
        self.tiles_layout = QHBoxLayout(self._tiles_container)
        self.tiles_layout.setContentsMargins(0, 0, 0, 0)
        self.tiles_layout.setSpacing(12)
        layout.addWidget(self._tiles_container, 1)

        self._tiles_opacity = QGraphicsOpacityEffect(self._tiles_container)
        self._tiles_container.setGraphicsEffect(self._tiles_opacity)

        # Sits on the visual left (last widget added ends up leftmost under
        # RTL mirroring) and should display a left-pointing arrow, hence `›`
        # here to mirror into `‹` - see the comment on prev_button above.
        self.next_button = QPushButton("›")
        self.next_button.setObjectName("carouselArrow")
        self.next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_button.clicked.connect(self._go_next)
        layout.addWidget(self.next_button)

        self._render_group(animate=False)

    def _group_count(self) -> int:
        return max(1, (len(self._items) + _GROUP_SIZE - 1) // _GROUP_SIZE)

    def _go_prev(self) -> None:
        if self._current_group > 0:
            self._current_group -= 1
            self._render_group()

    def _go_next(self) -> None:
        if self._current_group < self._group_count() - 1:
            self._current_group += 1
            self._render_group()

    def _render_group(self, animate: bool = True) -> None:
        if not animate:
            self._rebuild_tiles()
            return

        fade_out = QPropertyAnimation(self._tiles_opacity, b"opacity", self)
        fade_out.setDuration(110)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade_out.finished.connect(self._rebuild_and_fade_in)
        self._fade_animation = fade_out
        fade_out.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _rebuild_and_fade_in(self) -> None:
        self._rebuild_tiles()
        fade_in = QPropertyAnimation(self._tiles_opacity, b"opacity", self)
        fade_in.setDuration(160)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_animation = fade_in
        fade_in.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _rebuild_tiles(self) -> None:
        while self.tiles_layout.count():
            item = self.tiles_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        start = self._current_group * _GROUP_SIZE
        for title, icon_file, page_index in self._items[start : start + _GROUP_SIZE]:
            tile = _Tile(title, icon_file, page_index)
            tile.clicked.connect(lambda _checked=False, idx=page_index: self.tile_clicked.emit(idx))
            self.tiles_layout.addWidget(tile)

        self.prev_button.setEnabled(self._current_group > 0)
        self.next_button.setEnabled(self._current_group < self._group_count() - 1)
