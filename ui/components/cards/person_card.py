"""Person portrait card — square MediaCard with a portrait glyph."""
from __future__ import annotations

from ui.components.cards.media_card import MediaCard


class PersonCard(MediaCard):
    def __init__(self, width: int = 160, parent=None) -> None:
        super().__init__(width, kind="person", parent=parent)
