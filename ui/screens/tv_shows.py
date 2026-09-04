"""TV Shows — grid plus per-show season/episode detail on the route.

Episode-level resume is exposed from the show card via the shared
actions layer (details → play/resume)."""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_grid import MediaGridView


class TvShowsScreen(BaseScreen, ScreenActions):
    SORTS = [
        ("title", "Title"),
        ("year", "Year"),
    ]

    def __init__(self, context) -> None:
        super().__init__(context)
        self._grid = None
        self._sort_combo = None
        self._header = None
        self._all = []

    def empty_title(self) -> str:
        return "No TV Shows Yet"

    def empty_subtitle(self) -> str:
        return "Series you add to your library will show up here, ready "
        "to pick up where you left off."

    def page_title(self) -> str:
        return "TV Shows"

    def load(self) -> None:
        header = PageHeader("TV Shows", subtitle="{n} shows")
        self.add_to_content(header)
        self._header = header
        sort_combo = QComboBox()
        for value, label in self.SORTS:
            sort_combo.addItem(label, value)
        sort_combo.setFixedWidth(150)
        header.add_control(sort_combo)
        sort_combo.currentIndexChanged.connect(lambda _=0: self._apply_sort())
        self._sort_combo = sort_combo
        grid = MediaGridView(self, parent=self.container)
        self.add_to_content(grid, stretch=1)
        self._grid = grid
        self.start_async_load(lambda s: (data.fetch_tv_shows(s),))

    def handle_data(self, payload) -> None:
        self._all = list(payload[0])
        self._apply_sort()

    def _apply_sort(self) -> None:
        sort = self._sort_combo.currentData() or "title"
        items = list(self._all)
        if sort == "year":
            items.sort(key=lambda e: (e.year is None, -(e.year or 0), e.title))
        self._header.set_count(len(items))
        if not items:
            self.show_empty()
            return
        self.show_content()
        self._grid.set_entities(items)

    def refresh_theme(self) -> None:
        self._grid.refresh_artwork()
