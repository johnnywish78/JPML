"""Movies — responsive grid, search filter, sorting (title/year/most
watched/recently played). Rating sorting is intentionally absent (no
rating data in the frozen backend)."""
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QLineEdit, QWidget

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_grid import MediaGridView


class MoviesScreen(BaseScreen, ScreenActions):
    SORTS = [
        ("title", "Title"),
        ("recently_added", "Recently Added"),
        ("recently_played", "Recently Played"),
        ("year", "Year"),
        ("most_watched", "Most Watched"),
    ]

    def __init__(self, context) -> None:
        super().__init__(context)

    def empty_title(self) -> str:
        return "No Movies Yet"

    def empty_subtitle(self) -> str:
        return "Movies you add to your library will show up here."

    def page_title(self) -> str:
        return "Movies"

    def load(self) -> None:
        header = PageHeader("Movies", subtitle="{n} movies")
        self.add_to_content(header)
        self._header = header
        sort_combo = QComboBox()
        for value, label in self.SORTS:
            sort_combo.addItem(label, value)
        sort_combo.setFixedWidth(170)
        header.add_control(sort_combo)
        filter_edit = QLineEdit()
        filter_edit.setPlaceholderText("Filter titles…")
        filter_edit.setFixedWidth(220)
        header.add_control(filter_edit)
        grid = MediaGridView(self, parent=self.container)
        self.add_to_content(grid, stretch=1)
        self._grid = grid
        self._sort_combo = sort_combo
        self._filter_edit = filter_edit
        self._all: list = []
        sort_combo.currentIndexChanged.connect(lambda _=0: self._apply_filter_sort())
        filter_edit.textChanged.connect(lambda _t="": self._apply_filter_sort())
        self.start_async_load(lambda s: (data.fetch_movies(s),))

    def handle_data(self, payload) -> None:
        movies = payload[0]
        self._all = movies
        self._apply_filter_sort()

    def _apply_filter_sort(self) -> None:
        query = self._filter_edit.text().strip().lower() if self._filter_edit else ""
        sort = self._sort_combo.currentData() or "title"
        filtered = self._all
        if query:
            filtered = [m for m in filtered if query in (m.title or "").lower()]
        if sort != "title":
            try:
                filtered = list(filtered)
                if sort == "year":
                    filtered.sort(key=lambda e: (e.year is None, -(e.year or 0), e.title))
                elif sort == "most_watched" or sort == "recently_played":
                    if sort == "most_watched":
                        counts = self._play_counts()
                        filtered.sort(key=lambda e: (-counts.get(e.key(), 0), e.title))
                    else:
                        order = self._recent_order()
                        filtered.sort(
                            key=lambda e: (
                                1 << 30 if e.key() not in order else order[e.key()],
                                e.title,
                            )
                        )
            except Exception:
                pass
        self._header.set_count(len(filtered))
        if not filtered:
            self.show_empty()
            return
        self.show_content()
        self._grid.set_entities(filtered)

    def _play_counts(self):
        rows = data._safe(lambda: self.context.services.statistics.most_watched(1000), [])
        return {(str(r["media_type"]), int(r["media_id"])): int(r["plays"]) for r in rows}

    def _recent_order(self):
        rows = data._safe(lambda: self.context.services.statistics.recent_playback(1000), [])
        order = {}
        for i, row in enumerate(rows):
            order[(str(row["media_type"]), int(row["media_id"]))] = i
        return order

    def refresh_theme(self) -> None:
        self._grid.refresh_artwork()
