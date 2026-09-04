"""Home — hero plus dynamic rows; empty rows are hidden entirely."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.cards.album_card import AlbumCard
from ui.components.cards.media_card import MediaCard
from ui.components.cards.person_card import PersonCard
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.hero import Hero
from ui.components.media.media_row import CardFactory, MediaRow, SectionHeader
from ui.models import EntityRef


class HomeScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context, scrollable=True)
        self._rows: list[MediaRow] = []
        self._hero: Hero | None = None

    # -- content -------------------------------------------------------------

    def empty_title(self) -> str:
        return "Your library is empty"

    def empty_subtitle(self) -> str:
        return (
            "Add a folder containing your movies, TV shows or music to "
            "start building your personal media library."
        )

    def empty_action(self) -> str | None:
        return "+ Add Library Location"

    def empty_secondary_action(self) -> str | None:
        return "Manage Library"

    def empty_action_clicked(self) -> None:
        from ui.app.library_flow import scan_in_progress
        from PyQt6.QtWidgets import QApplication

        if scan_in_progress(QApplication.instance()):
            self._toast("A scan is already running")
            return
        path = self._pick_library_folder()
        if not path:
            return
        self.context.navigation.navigate("library", pending_path=str(path))

    def empty_secondary_action_clicked(self) -> None:
        self.context.navigation.navigate("library")

    def _pick_library_folder(self) -> str | None:
        """Real directory picker (seam for headless tests)."""
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path

        start = str(Path.home())
        path = QFileDialog.getExistingDirectory(
            self, "Choose a media folder", start
        )
        return str(path) if path else None

    def page_title(self) -> str:
        return "Home"

    def load(self) -> None:
        self.start_async_load(self._gather)

    def _gather(self, services) -> dict:
        return {
            "continue_watching": data.fetch_continue_watching(services),
            "recently_added": data.fetch_recently_added(services),
            "trending": data.fetch_trending(services),
            "movies": data.fetch_movies(services)[:12],
            "shows": data.fetch_tv_shows(services)[:12],
            "favorites": data.fetch_favorites(services)[:12],
        }

    def handle_data(self, payload: dict) -> None:
        self.clear_content()
        services = self.context.services
        if data.library_is_empty(services) and not payload["continue_watching"]:
            self.show_empty()
            return

        factory = CardFactory()
        factory._width = 160  # noqa: SLF001 — single fixed card size

        # -- hero ---------------------------------------------------------
        hero_ref = self._pick_hero(payload)
        if hero_ref is not None:
            self._hero = Hero(height=460)
            self._wire_hero(self._hero, hero_ref)
            self.add_to_content(self._hero)

        # -- rows ------------------------------------------------------------
        self._add_row("Continue Watching", payload["continue_watching"],
                      factory, kind="poster")
        self._add_row("Recently Added", payload["recently_added"], factory)
        self._add_row(
            "Trending in Your Library", payload["trending"], factory
        )
        self._add_row("Movies", payload["movies"], factory)
        self._add_row("TV Shows", payload["shows"], factory)
        self._add_row("Favorites", payload["favorites"], factory)
        self.show_content()

    def _pick_hero(self, payload: dict) -> EntityRef | None:
        for key in ("continue_watching", "trending", "recently_added",
                    "movies", "shows", "favorites"):
            items = payload.get(key) or []
            if items:
                return items[0]
        return None

    def _wire_hero(self, hero: Hero, ref: EntityRef) -> None:
        hero.play_clicked.connect(lambda: self.play_entity(ref))
        hero.details_clicked.connect(lambda: self.open_details(ref))
        hero.favorite_clicked.connect(lambda: self.entity_action(ref, "favorite"))
        hero.watchlist_clicked.connect(lambda: self.entity_action(ref, "watchlist"))
        hero.set_entity(ref)

    def _add_row(
        self,
        title: str,
        items: list[EntityRef],
        factory: CardFactory,
        kind: str = "poster",
    ) -> None:
        if not items:
            return  # hide the entire row when there is no data
        header = SectionHeader(title, more_label="See all →")
        self.add_to_content(header)
        row = MediaRow(factory, self.container)
        for entity in items:
            card = (
                MediaCard(factory.width, kind=entity.artwork_kind, parent=row)
            )
            card.set_entity(entity)
            row.add_card(card)
            self._wire_row_card(card, entity)
        more = header.more_button
        if more is not None:
            target = self._route_for(title)
            if target:
                more.clicked.connect(
                    lambda _=False, t=target: self.context.navigation.navigate(t)
                )
        self.add_to_content(row)
        self._rows.append(row)

    @staticmethod
    def _route_for(title: str) -> str | None:
        return {
            "Movies": "movies",
            "TV Shows": "tv_shows",
            "Favorites": "favorites",
            "Trending in Your Library": "trending",
        }.get(title)

    def _wire_row_card(self, card, entity: EntityRef) -> None:
        card.play_requested.connect(lambda ref: self.play_entity(ref))
        card.details_requested.connect(lambda ref: self.open_details(ref))
        card.action_requested.connect(
            lambda ref, action: self.entity_action(ref, action)
        )
        card.menu_requested.connect(
            lambda ref, pos: self.entity_context_menu(ref, pos)
        )

    def refresh_theme(self) -> None:
        for row in self._rows:
            for card in row.cards():
                card.refresh_artwork()
        if self._hero is not None:
            self._hero.refresh_backdrop()
