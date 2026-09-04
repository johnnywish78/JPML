"""Global Search — grouped results (Movies/TV/People/Music) with debounce.

Debounce is handled by the top bar (300 ms). This screen renders grouped
results for the active query and updates live as results change.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.cards.album_card import AlbumCard
from ui.components.cards.person_card import PersonCard
from ui.components.cards.media_card import MediaCard
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_row import CardFactory, MediaRow, SectionHeader


SECTION_ORDER = [
    ("Movies", "movie", MediaCard, "poster"),
    ("TV Shows", "tv", MediaCard, "poster"),
    ("People", "person", PersonCard, "person"),
    ("Music", None, None, "album"),  # albums + tracks combined
]


class SearchScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        self._query = ""  # must exist before BaseScreen builds empty widget
        self._rows: list[MediaRow] = []
        super().__init__(context)
        self._query = ""

    def empty_title(self) -> str:
        q = self._query
        return f"No results for “{q}”" if q else "Search your library"

    def empty_subtitle(self) -> str:
        return "Try a different title, person, artist or album."

    def page_title(self) -> str:
        return "Search"

    def on_activated(self) -> None:
        self._query = (
            self.context.navigation.current_route.params.get("query", "")
            if self.context.navigation.current_route
            else ""
        )
        if self._scan_in_progress():
            self._begin_watch_scan()
            self.show_scanning("Scanning your library…")
            return
        self._stop_watching_scan()
        self.load()

    def load(self) -> None:
        query = self._query
        self.start_async_load(lambda s: self._gather(s, query))

    def _gather(self, services, query: str):
        if not query:
            return {"movies": [], "tv": [], "people": [], "albums": [], "tracks": []}
        return {
            "movies": data.search_movies(services, query)[:40],
            "tv": data.search_tv_shows(services, query)[:40],
            "people": data.search_people(services, query)[:24],
            "albums": data.search_albums(services, query)[:40],
            "tracks": data.search_tracks(services, query)[:40],
        }

    def handle_data(self, payload: dict) -> None:
        self.clear_content()
        self._rows.clear()
        factory = CardFactory()
        factory._width = 170  # noqa: SLF001

        header = PageHeader(
            "Search", subtitle=f"Results for “{self._query}”" if self._query else ""
        )
        self.add_to_content(header)

        any_results = False
        if payload["movies"]:
            any_results = True
            self._section("Movies", payload["movies"], factory)
        if payload["tv"]:
            any_results = True
            self._section("TV Shows", payload["tv"], factory)
        if payload["people"]:
            any_results = True
            self._section("People", payload["people"], factory, "person")
        music = payload["albums"] + [
            EntityRef(
                kind="track",
                entity_id=t.entity_id,
                title=t.title,
                year=t.year,
                meta=t.meta,
                artwork_kind="album",
                extra={"album_name": t.album.title if t.album else ""}
                if t.album
                else {},
            )
            for t in payload["tracks"]
        ]
        if music:
            any_results = True
            self._section("Music", music, factory)

        if not any_results:
            self.show_empty()
            return
        self.show_content()

    def _section(self, title: str, items, factory, kind: str = "poster") -> None:
        header = SectionHeader(title)
        self.add_to_content(header)
        row = MediaRow(factory, self.container)
        for entity in items:
            card_cls = PersonCard if kind == "person" else (
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

    def refresh_theme(self) -> None:
        for row in self._rows:
            for card in row.cards():
                card.refresh_artwork()


from ui.models import EntityRef  # noqa: E402
