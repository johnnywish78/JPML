"""The single shared media card used by every screen that shows media.

Pure presentation: the card renders an EntityRef and emits interaction
signals. Screens own the behavior (play/details/favorites/menus) via
the injected callbacks/signals.
"""
from __future__ import annotations

from PyQt6.QtCore import (
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.components.common.button import IconButton
from ui.components.media.artwork import Artwork
from ui.models import EntityRef
from ui.themes.tokens import Motion, Radius, Spacing, Typography


class MediaCard(QFrame):
    play_requested = pyqtSignal(object)  # EntityRef
    details_requested = pyqtSignal(object)
    action_requested = pyqtSignal(object, str)  # EntityRef, action
    menu_requested = pyqtSignal(object, object)  # EntityRef, QPoint (global)

    KIND_SIZES = {
        "poster": (2, 3),
        "album": (1, 1),
        "artist": (1, 1),
        "person": (1, 1),
        "backdrop": (16, 9),
    }

    KIND_GLYPHS = {
        "poster": "▦",
        "album": "♫",
        "artist": "🎵",
        "person": "👤",
        "backdrop": "▭",
    }

    def __init__(self, width: int = 160, kind: str = "poster", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFrame")
        self._width = width
        self._entity: EntityRef | None = None
        self._kind = kind if kind in self.KIND_SIZES else "poster"

        ratio = self.KIND_SIZES[self._kind]
        art_h = int(width * ratio[1] / ratio[0])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Spacing.S, Spacing.S, Spacing.S, Spacing.S)
        layout.setSpacing(Spacing.S)

        self._art = Artwork(width - Spacing.S * 2, art_h,
                            kind=self._kind, kind_glyph=self.KIND_GLYPHS[self._kind])

        self._overlay = QWidget()
        ol = QHBoxLayout(self._overlay)
        ol.setContentsMargins(0, Spacing.M, 0, Spacing.M)
        ol.setSpacing(Spacing.S)
        self._btn_play = IconButton("▶", "Play", self._overlay)
        self._btn_details = IconButton("ℹ", "Details", self._overlay)
        self._btn_fav = IconButton("♥", "Favorite", self._overlay)
        self._btn_fav.setFixedWidth(28)
        self._btn_list = IconButton("+", "Add to Watchlist", self._overlay)
        ol.addWidget(self._btn_play)
        ol.addStretch(1)
        ol.addWidget(self._btn_details)
        ol.addWidget(self._btn_fav)
        ol.addWidget(self._btn_list)
        self._overlay.hide()
        self._fade = QPropertyAnimation(self._overlay, b"windowOpacity")
        self._fade.setDuration(Motion.MICRO)

        self._btn_play.clicked.connect(self._emit_play)
        self._btn_details.clicked.connect(self._emit_details)
        self._btn_fav.clicked.connect(lambda: self.action_requested.emit(self._entity, "favorite"))
        self._btn_list.clicked.connect(lambda: self.action_requested.emit(self._entity, "watchlist"))

        self._title = QLabel("")
        self._title.setStyleSheet(
            f"font-size: {Typography.CARD_PX}px; font-weight: {500}; "
            "background: transparent;"
        )
        self._title.setFixedHeight(Typography.CARD_PX + 6)
        self._title.setToolTip("")
        self._meta = QLabel("")
        self._meta.setObjectName("SecondaryLabel")
        self._meta.setStyleSheet(
            f"font-size: {Typography.METADATA_PX}px; background: transparent;"
        )
        self._meta.setFixedHeight(Typography.METADATA_PX + 4)

        self._progress = _ProgressIndicator()
        self._progress.hide()

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedWidth(width)
        self._build_body(layout)

    def _build_body(self, layout: QVBoxLayout) -> None:
        layout.addWidget(self._art, 0, Qt.AlignmentFlag.AlignHCenter)

        # hover overlay covers the artwork area
        self._overlay.setParent(self._art)
        self._reposition_overlay()

        layout.addWidget(self._title)
        layout.addWidget(self._meta)
        layout.addWidget(self._progress)

    def _reposition_overlay(self) -> None:
        if self._art is not None:
            self._overlay.setGeometry(self._art.rect().adjusted(0, 0, 0, 0))
            self._overlay.raise_()

    # ------------------------------------------------------------------

    def _tokens(self):
        try:
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            state = getattr(app, "jpml_state", None) if app else None
            return getattr(state, "theme", None)
        except Exception:
            return None

    def set_entity(self, entity: EntityRef) -> None:
        """Render an EntityRef into this card. The card's aspect (kind)
        is fixed at construction to keep row geometry stable; artwork and
        source come from the ref."""
        self._entity = entity
        tokens = self._tokens()
        self._art.set_source(self._resolve_source(entity), tokens)
        self._title.setText(entity.title)
        self._title.setToolTip(entity.title)
        self._meta.setText(entity.meta)
        self._progress.set_visible(entity.progress is not None)
        if entity.progress is not None:
            self._progress.set_progress(min(1.0, max(0.0, entity.progress)), entity.progress_label)
        else:
            self._progress.clear()
        # favorite / watchlist affordances
        self._btn_fav.setText("♥" if entity.is_favorite else "♡")
        self._btn_fav.setToolTip("Remove Favorite" if entity.is_favorite else "Favorite")
        self._btn_list.setText("−" if entity.in_watchlist else "+")
        self._btn_list.setToolTip(
            "Remove from Watchlist" if entity.in_watchlist else "Add to Watchlist"
        )
        self.adjustSize()
        self._reposition_overlay()
        self.updateGeometry()

    def _resolve_source(self, entity: EntityRef) -> str | None:
        return entity.artwork.get("local_path") if entity.artwork else None

    def refresh_artwork(self) -> None:
        if self._entity is not None:
            self._art.set_source(self._resolve_source(self._entity), self._tokens())

    # -- hover -------------------------------------------------------------

    def enterEvent(self, event) -> None:  # noqa: N802
        self._overlay.show()
        self._overlay.lower()
        self._overlay.raise_()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        if not self._fade.state() == self._fade.State.Running:
            self._fade.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._fade.setStartValue(self._fade.currentValue())
        self._fade.setEndValue(0.0)
        self._fade.start()
        super().leaveEvent(event)

    # -- keyboard / mouse -----------------------------------------------------

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._emit_details()
        elif key == Qt.Key.Key_Menu or key == Qt.Key.Key_F10:
            self._emit_menu()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            self._emit_menu()
        else:
            super().mousePressEvent(event)

    def _emit_play(self) -> None:
        if self._entity is not None:
            self.play_requested.emit(self._entity)

    def _emit_details(self) -> None:
        if self._entity is not None:
            self.details_requested.emit(self._entity)

    def _emit_menu(self) -> None:
        if self._entity is not None:
            pos = self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2))
            self.menu_requested.emit(self._entity, pos)

    def is_progress_card(self) -> bool:
        return self._progress.is_visible()


class _ProgressIndicator(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(4)
        self._hidden = True
        self._fraction = 0.0
        self._label = ""
        from PyQt6.QtGui import QBrush, QColor

        self.setVisible(False)

    def set_visible(self, visible: bool) -> None:
        self._hidden = not visible
        self.update()

    def set_progress(self, fraction: float, label: str) -> None:
        self._fraction = fraction
        self._label = label
        self.update()

    def clear(self) -> None:
        self._fraction = 0.0
        self._label = ""
        self.update()

    def is_visible(self) -> bool:
        return not self._hidden

    def paintEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtGui import QBrush, QColor, QPainter

        if self._hidden:
            return
        painter = QPainter(self)
        rect = self.rect().adjusted(0, 0, 0, 0)
        radius = 2
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#2A2F3B"))
        painter.drawRoundedRect(QRectF(0, 0, float(rect.width()), float(rect.height())), radius, radius)
        if self._fraction > 0:
            painter.setBrush(QColor("#D7263D"))
            w = float(rect.width()) * self._fraction
            painter.drawRoundedRect(QRectF(0, 0, w, float(rect.height())), radius, radius)
        painter.end()

    def sizeHint(self):
        return QSize(120, 4)
