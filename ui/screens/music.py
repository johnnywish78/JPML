"""Music — Artists, Albums, Tracks, Recently Played sections."""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.cards.album_card import AlbumCard, ArtistCard
from ui.components.cards.media_card import MediaCard
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_grid import MediaGridView
from ui.components.media.media_row import CardFactory, MediaRow, SectionHeader
from ui.models import EntityRef


class MusicScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)
        self._rows: list[MediaRow] = []
        self._grids: list[MediaGridView] = []

    def empty_title(self) -> str:
        return "No Music Yet"

    def empty_subtitle(self) -> str:
        return "Music files you add to your library will appear here, "
        "organized by artist, album and track."

    def page_title(self) -> str:
        return "Music"

    def load(self) -> None:
        self.add_to_content(PageHeader("Music", subtitle="Artists · Albums · Tracks"))
        self.start_async_load(self._gather)

    def _gather(self, services):
        return {
            "artists": data.fetch_artists(services),
            "albums": data.fetch_albums(services),
            "tracks": data.fetch_tracks(services),
            "recent": data.fetch_recently_played_music(services),
        }

    def handle_data(self, payload: dict) -> None:
        self.clear_content()
        if not any(payload.values()):
            self.show_empty()
            return
        self.add_to_content(PageHeader("Music", subtitle="Artists · Albums · Tracks"))
        factory = CardFactory()
        factory._width = 160  # noqa: SLF001
        if payload["recent"]:
            self._row("Recently Played", payload["recent"], factory, "album")
        if payload["artists"]:
            self._artists(payload["artists"], factory)
        if payload["albums"]:
            self._row("Albums", payload["albums"], factory, "album")
        if payload["tracks"]:
            self._row("Tracks", payload["tracks"][:40], factory, "album")
        self.show_content()

    def _row(self, title: str, items: list[EntityRef], factory, kind: str) -> None:
        header = SectionHeader(title)
        self.add_to_content(header)
        row = MediaRow(factory, self.container)
        for entity in items:
            card_cls = ArtistCard if kind == "artist" else (
                AlbumCard if kind == "album" else MediaCard
            )
            card = card_cls(factory.width, parent=row)
            card.set_entity(entity)
            row.add_card(card)
            card.play_requested.connect(lambda ref: self.play_entity(ref))
            card.details_requested.connect(lambda ref: self.open_details(ref))
            card.action_requested.connect(
                lambda ref, action: self.entity_action(ref, action)
            )
            card.menu_requested.connect(
                lambda ref, pos: self.entity_context_menu(ref, pos)
            )
        self.add_to_content(row)
        self._rows.append(row)

    def _artists(self, artists: list[EntityRef], factory) -> None:
        header = SectionHeader("Artists")
        self.add_to_content(header)
        grid = MediaGridView(self, parent=self.container, card_cls=ArtistCard, card_width=150)
        grid.set_entities(artists)  # wires play/details/actions/menu for the screen
        self.add_to_content(grid)
        self._grids.append(grid)

    def refresh_theme(self) -> None:
        for row in self._rows:
            for card in row.cards():
                card.refresh_artwork()
        for grid in self._grids:
            grid.refresh_artwork()
