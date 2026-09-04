"""Album / artist / backdrop cards — MediaCard variants."""
from __future__ import annotations

from ui.components.cards.media_card import MediaCard


class AlbumCard(MediaCard):
    def __init__(self, width: int = 160, parent=None) -> None:
        super().__init__(width, kind="album", parent=parent)


class ArtistCard(MediaCard):
    def __init__(self, width: int = 160, parent=None) -> None:
        super().__init__(width, kind="artist", parent=parent)
