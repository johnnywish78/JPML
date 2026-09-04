"""Horizontal scrollable card row — one implementation, used everywhere."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.components.cards.media_card import MediaCard
from ui.models import EntityRef
from ui.themes.tokens import Spacing


class CardFactory:
    def __init__(self) -> None:
        self._width = 160

    @property
    def width(self) -> int:
        return self._width

    def card(self, parent: QWidget) -> MediaCard:
        return MediaCard(self._width, parent)


class MediaRow(QScrollArea):
    """A horizontally scrolling strip of cards.

    * ``add_card(card)`` appends a card.
    * The row is fixed height so stacking many rows never jumps.
    """

    def __init__(self, factory: CardFactory, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(self.frameShape())
        self.setStyleSheet("QScrollArea { border: none; }")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.factory = factory
        self._content = QWidget()
        self._layout = QHBoxLayout(self._content)
        self._layout.setContentsMargins(2, 2, 2, 6)
        self._layout.setSpacing(Spacing.L)
        self.setWidget(self._content)
        # reserve the fixed geometry of a card to avoid vertical jumps
        ratio_w, ratio_h = 2, 3
        art_h = int(factory.width * ratio_h / ratio_w)
        card_h = art_h + factory.width * 0 + 8 + 20 + 14 + 6 + 12 + 8 + 14 + 8
        self.setFixedHeight(card_h)
        self._cards: list[MediaCard] = []

    def add_card(self, card: MediaCard) -> None:
        self._cards.append(card)
        self._layout.addWidget(card)

    def clear(self) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def cards(self) -> list[MediaCard]:
        return self._cards

    def _adapt(self) -> None:
        pass


class SectionHeader(QWidget):
    """Row title with optional 'more' disclosure."""

    def __init__(self, title: str, more_label: str | None = None, parent=None) -> None:
        from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton

        super().__init__(parent)
        self._more: "QPushButton | None" = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, Spacing.M)
        label = QLabel(title)
        label.setStyleSheet(
            "font-size: 18px; font-weight: 600; background: transparent;"
        )
        layout.addWidget(label)
        layout.addStretch(1)
        if more_label:
            self._more = QPushButton(more_label)
            self._more.setStyleSheet(
                "border: none; background: transparent; color: inherit; "
                "font-size: 13px; padding: 4px 8px;"
            )
            layout.addWidget(self._more)

    @property
    def more_button(self) -> QPushButton | None:
        return self._more
