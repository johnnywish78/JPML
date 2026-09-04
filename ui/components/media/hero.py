"""Cinematic hero strip: painted backdrop, gradient, title, actions."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.models import EntityRef
from ui.themes.tokens import Spacing, Typography


class Hero(QFrame):
    play_clicked = pyqtSignal()
    details_clicked = pyqtSignal()
    favorite_clicked = pyqtSignal()
    watchlist_clicked = pyqtSignal()

    def __init__(self, height: int = 500, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self._backdrop: QPixmap | None = None
        self._backdrop_key: str | None = None
        self._content_key: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.XXL3, 0, Spacing.XXL3, Spacing.XXL4)
        layout.setSpacing(0)
        layout.addStretch(2)

        self._title = QLabel("")
        self._title.setStyleSheet(
            f"font-size: {Typography.HERO_PX}px; font-weight: 700; "
            "color: #F5F5F7; background: transparent;"
        )
        self._title.setWordWrap(True)

        self._meta = QLabel("")
        self._meta.setStyleSheet(
            f"font-size: {Typography.METADATA_PX + 2}px; color: #C9CDD6; "
            "background: transparent; margin-top: 10px;"
        )

        self._overview = QLabel("")
        self._overview.setStyleSheet(
            f"font-size: {Typography.METADATA_PX + 1}px; color: #A7ABB5; "
            "background: transparent; margin-top: 16px;"
        )
        self._overview.setWordWrap(True)
        self._overview.setFixedWidth(640)

        layout.addWidget(self._title)
        layout.addWidget(self._meta)
        layout.addSpacing(Spacing.S)
        layout.addWidget(self._overview)
        layout.addSpacing(Spacing.XL)

        actions = QHBoxLayout()
        actions.setSpacing(Spacing.M)
        self._btn_play = QPushButton("▶  Play")
        self._btn_play.setObjectName("PrimaryButton")
        self._btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_details = QPushButton("Details")
        self._btn_details.setObjectName("GhostButton")
        self._btn_details.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_fav = QPushButton("♡  Favorite")
        self._btn_fav.setObjectName("GhostButton")
        self._btn_watch = QPushButton("+  Watchlist")
        self._btn_watch.setObjectName("GhostButton")
        for button in (self._btn_fav, self._btn_watch):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        actions.addWidget(self._btn_play)
        actions.addWidget(self._btn_details)
        actions.addWidget(self._btn_fav)
        actions.addWidget(self._btn_watch)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(0)

        self._btn_play.clicked.connect(self.play_clicked)
        self._btn_details.clicked.connect(self.details_clicked)
        self._btn_fav.clicked.connect(self.favorite_clicked)
        self._btn_watch.clicked.connect(self.watchlist_clicked)

    # -- public API ----------------------------------------------------------

    def set_entity(self, ref: EntityRef, tokens=None) -> None:
        self._content_key = ref.key().__str__()
        self._title.setText(ref.title)
        parts: list[str] = []
        if ref.year:
            parts.append(str(ref.year))
        if ref.meta:
            parts.extend(p for p in ref.meta.split(" · ") if p)
        self._meta.setText(" · ".join(dict.fromkeys(parts)))
        self._overview.setText(ref.overview or "")
        self._btn_fav.setText("♥  Favorite" if ref.is_favorite else "♡  Favorite")
        self._btn_watch.setText("−  Watchlist" if ref.in_watchlist else "+  Watchlist")
        self._load_backdrop(ref, tokens)

    def clear(self) -> None:
        self._title.setText("")
        self._meta.setText("")
        self._overview.setText("")
        self._backdrop = None
        self._backdrop_key = None
        self._content_key = None
        self.update()

    def refresh_backdrop(self) -> None:
        self._load_backdrop_pending()

    # -- backdrop -----------------------------------------------------------------

    def _backdrop_source(self, ref: EntityRef) -> str | None:
        backdrop = (ref.extra or {}).get("backdrop")
        if isinstance(backdrop, dict):
            raw = backdrop.get("local_path")
            if raw and self._exists(raw):
                return str(raw)
        if ref.artwork:
            raw = ref.artwork.get("local_path")
            if raw and self._exists(raw):
                return str(raw)
        return None

    @staticmethod
    def _exists(path: str) -> bool:
        from pathlib import Path

        return Path(path).is_file()

    def _load_backdrop(self, ref: EntityRef, tokens=None) -> None:
        from ui.utils import image_cache

        source = self._backdrop_source(ref)
        key = image_cache.key_for(source, self._backdrop_size())
        self._backdrop_key = key
        cached = image_cache.cached(key)
        if cached is not None and not cached.isNull():
            self._backdrop = cached
        else:
            image_cache.get_pixmap(source, self._backdrop_size(), None, tokens)
        self.update()

    def _load_backdrop_pending(self) -> None:
        key = getattr(self, "_backdrop_key", None)
        if key:
            from ui.utils import image_cache

            cached = image_cache.cached(key)
            if cached is not None and not cached.isNull():
                self._backdrop = cached
                self.update()

    def _backdrop_size(self) -> QSize:
        return QSize(max(960, self.width()), max(480, self.height()))

    # -- painting ---------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0B0D12"))
        if self._backdrop is not None and not self._backdrop.isNull():
            scaled = self._backdrop.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            painter.drawPixmap(
                self.rect(),
                scaled,
                scaled.rect().adjusted(x, y, x, y),
            )
        else:
            # quiet gradient placeholder (no fake imagery)
            base = QLinearGradient(0, 0, self.width(), self.height())
            base.setColorAt(0.0, QColor("#151820"))
            base.setColorAt(1.0, QColor("#0B0D12"))
            painter.fillRect(self.rect(), QBrush(base))

        # cinematic gradients — always (readable over real backdrops)
        def _c(hex_color, alpha):
            from PyQt6.QtGui import QColor as _QColor
            c = _QColor(hex_color)
            return _QColor(c.red(), c.green(), c.blue(), alpha)

        vertical = QLinearGradient(0, 0, 0, self.height())
        vertical.setColorAt(0.0, _c("#08090C", 110))
        vertical.setColorAt(0.4, _c("#08090C", 50))
        vertical.setColorAt(1.0, _c("#08090C", 248))
        painter.fillRect(self.rect(), QBrush(vertical))
        horizontal = QLinearGradient(0, 0, self.width(), 0)
        horizontal.setColorAt(0.0, _c("#08090C", 205))
        horizontal.setColorAt(0.45, _c("#08090C", 45))
        horizontal.setColorAt(1.0, _c("#08090C", 0))
        painter.fillRect(self.rect(), QBrush(horizontal))
        painter.end()
