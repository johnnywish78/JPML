"""Artwork display widget with stable aspect ratio and async loading."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QSizePolicy

from ui.themes.tokens import Radius
from ui.utils.image_cache import get_pixmap


class Artwork(QFrame):
    """Shows a fixed-aspect artwork area.

    * width/height are maintained by the parent (fixed size) — this
      widget only fills and center-crops, so layouts never jump.
    * ``kind_glyph`` is drawn on the placeholder when no image exists,
      so an empty library still looks intentional.
    """

    def __init__(
        self,
        width: int,
        height: int,
        *,
        kind: str = "poster",
        kind_glyph: str = "",
        rounded: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._width = width
        self._height = height
        self._kind = kind
        self._kind_glyph = kind_glyph
        self._pixmap: QPixmap | None = None
        if rounded:
            self._clip_radius = Radius.CARD
        else:
            self._clip_radius = 0
        self.setMinimumSize(width, height)
        if width > 0:
            self.setFixedSize(width, height)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed if width > 0 else QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed if height > 0 else QSizePolicy.Policy.Expanding,
        )

    # -- public API ----------------------------------------------------------

    def set_kind(self, kind: str, glyph: str) -> None:
        self._kind = kind
        self._kind_glyph = glyph

    def set_source(self, source: str | None, tokens=None) -> None:
        if source == getattr(self, "_source", object()):
            return
        self._source = source
        tokens = tokens or self._tokens()
        self._pixmap = get_pixmap(
            source,
            QSize(self._width, self._height),
            self._on_loaded,
            tokens,
        )
        self.update()

    def refresh(self) -> None:
        """Re-read the cache (used after a theme switch or async load)."""
        from ui.utils import image_cache

        source = getattr(self, "_source", None)
        key = image_cache.key_for(
            source, QSize(self._width, self._height)
        )
        cached = image_cache.cached(key)
        if cached is not None and not cached.isNull():
            self._pixmap = cached
        else:
            self._pixmap = image_cache.get_pixmap(
                source, QSize(self._width, self._height), None, self._tokens()
            )
        self.update()

    def _tokens(self):
        try:
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            manager = getattr(getattr(app, "jpml_state", None), "theme", None) if app else None
            return manager.tokens if manager else None
        except Exception:
            return None

    def _on_loaded(self, key: str) -> None:
        from ui.utils import image_cache

        cached = image_cache.cached(key)
        if cached is not None and not cached.isNull():
            self._pixmap = cached
            self.update()

    @property
    def has_image(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    # -- painting ----------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtGui import QBrush, QColor, QPainterPath
        from PyQt6.QtCore import QRectF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        region = self.rect()
        if self._clip_radius:
            path = QPainterPath()
            path.addRoundedRect(QRectF(region), self._clip_radius, self._clip_radius)
            painter.setClipPath(path)

        if self._pixmap is not None and not self._pixmap.isNull():
            target = self.rect()
            scaled = self._pixmap.scaled(
                target.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - target.width()) // 2
            y = (scaled.height() - target.height()) // 2
            painter.drawPixmap(target, scaled, scaled.rect().adjusted(x, y, x, y))
        else:
            # JPML placeholder: subtle surface + glyph
            dark = True
            try:
                tokens = self._tokens()
                if tokens is not None:
                    dark = tokens.name == "dark"
            except Exception:
                pass
            painter.fillRect(region, QColor("#1A1D26" if dark else "#E8E9ED"))
            if self._kind_glyph:
                font = QFont("Sans Serif")
                font.setPixelSize(max(14, self._width // 4))
                font.setWeight(QFont.Weight.Thin)
                painter.setFont(font)
                painter.setPen(QColor("#39404E" if dark else "#AEB2BC"))
                painter.drawText(region, Qt.AlignmentFlag.AlignCenter, self._kind_glyph)
        painter.end()
