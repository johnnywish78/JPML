"""Responsive media grid: same card component everywhere, column count
derived from available width and a minimum card width."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QFrame,
    QVBoxLayout,
    QWidget,
)

from ui.components.cards.media_card import MediaCard
from ui.models import EntityRef
from ui.themes.tokens import Spacing


class MediaGridView(QScrollArea):
    """Grid of EntityRef cards that reflows on resize."""

    def __init__(
        self,
        screen,
        *,
        card_cls: type[MediaCard] = MediaCard,
        card_width: int = 160,
        gap: int = Spacing.L,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.screen = screen
        self.card_cls = card_cls
        self.card_width = card_width
        self.gap = gap
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QGridLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, Spacing.M)
        self._layout.setHorizontalSpacing(gap)
        self._layout.setVerticalSpacing(gap)
        self._layout.setSpacing(gap)
        self.setWidget(self._content)
        self._cards: list[MediaCard] = []
        self._entities: list[EntityRef] = []

    def set_entities(self, entities: list[EntityRef]) -> None:
        self._entities = list(entities)
        self.clear()
        for entity in self._entities:
            card = self._make_card(entity)
            self._cards.append(card)
        self._relayout()

    def _make_card(self, entity: EntityRef) -> MediaCard:
        card = self.card_cls(self.card_width, self._content)
        card.set_entity(entity)
        self._wire(card, entity)
        return card

    def _wire(self, card: MediaCard, entity: EntityRef) -> None:
        card.play_requested.connect(
            lambda ref: self.screen.play_entity(ref)
        )
        card.details_requested.connect(
            lambda ref: self.screen.open_details(ref)
        )
        card.action_requested.connect(
            lambda ref, action: self.screen.entity_action(ref, action)
        )
        card.menu_requested.connect(
            lambda ref, pos: self.screen.entity_context_menu(ref, pos)
        )

    def clear(self) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

    def _relayout(self) -> None:
        # clear grid
        for card in self._cards:
            self._layout.removeWidget(card)
        available = max(320, self.width() - 8)
        cols = max(1, (available + self.gap) // (self.card_width + self.gap))
        for index, card in enumerate(self._cards):
            row, col = divmod(index, cols)
            self._layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop)
        self._layout.setRowStretch(len(self._cards) // cols + 1, 1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._cards:
            self._relayout()

    def refresh_artwork(self) -> None:
        for card in self._cards:
            card.refresh_artwork()
