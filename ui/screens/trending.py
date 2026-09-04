"""Trending — local, deterministic; labeled honestly."""
from __future__ import annotations

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_grid import MediaGridView


class TrendingScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)

    def empty_title(self) -> str:
        return "Nothing Trending Yet"

    def empty_subtitle(self) -> str:
        return "Trending is computed from playback activity in your own "
        "library — play a few things and this fills in."

    def page_title(self) -> str:
        return "Trending"

    def load(self) -> None:
        header = PageHeader(
            "Trending in Your Library",
            subtitle="Based on your recent playback",
        )
        self.add_to_content(header)
        self._grid = MediaGridView(self, parent=self.container)
        self.add_to_content(self._grid, stretch=1)
        self.start_async_load(lambda s: (data.fetch_trending(s),))

    def handle_data(self, payload) -> None:
        items = payload[0]
        if not items:
            self.show_empty()
            return
        self.show_content()
        self._grid.set_entities(items)

    def refresh_theme(self) -> None:
        self._grid.refresh_artwork()
