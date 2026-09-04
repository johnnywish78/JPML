"""Watchlist — independent from favorites."""
from __future__ import annotations

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_grid import MediaGridView


class WatchlistScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)

    def empty_title(self) -> str:
        return "Your Watchlist is Empty"

    def empty_subtitle(self) -> str:
        return "Movies and shows you want to watch will appear here."

    def empty_action(self) -> str | None:
        return "Browse Movies"

    def page_title(self) -> str:
        return "Watchlist"

    def load(self) -> None:
        header = PageHeader("Watchlist", subtitle="{n} items")
        self.add_to_content(header)
        self._header = header
        self._grid = MediaGridView(self, parent=self.container)
        self.add_to_content(self._grid, stretch=1)
        self.start_async_load(lambda s: (data.fetch_watchlist(s),))

    def handle_data(self, payload) -> None:
        items = payload[0]
        self._header.set_count(len(items))
        if not items:
            self.show_empty()
            return
        self.show_content()
        self._grid.set_entities(items)

    def refresh_theme(self) -> None:
        self._grid.refresh_artwork()

    def empty_action_clicked(self) -> None:
        self.context.navigation.navigate("movies")
