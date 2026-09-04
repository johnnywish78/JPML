"""Recommendations — deterministic genre-overlap strategy.

No invented reasons are shown beyond what the backend provides; the
current reference item is excluded from the results.
"""
from __future__ import annotations

import random

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_grid import MediaGridView


class RecommendationsScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)
        self._reference = None

    def empty_title(self) -> str:
        return "No Recommendations Yet"

    def empty_subtitle(self) -> str:
        return "Recommendations are based on the genres of what you've "
        "watched and favorited. Build up your library and this appears."

    def page_title(self) -> str:
        return "Recommended For You"

    def load(self) -> None:
        self._pick_reference()
        self.start_async_load(lambda s: (self._reference,))

    def _pick_reference(self) -> None:
        """Reference = most recently played, else most-favorited, else None.
        Never invent a reason — only used to scope the backend strategy."""
        services = self.context.services
        try:
            recent = services.statistics.recent_playback(1)
            if recent:
                row = recent[0]
                if row["media_type"] in ("movie", "tv"):
                    self._reference = self.context.navigation and _ref_from_row(
                        services, row
                    )
                    return
        except Exception:
            pass
        try:
            favs = services.favorites.list()
            for entry in favs:
                if entry.entity_type in ("movie", "tv"):
                    ref = _ref_from_entry(services, entry)
                    if ref is not None:
                        self._reference = ref
                        return
        except Exception:
            pass
        self._reference = None

    def handle_data(self, payload) -> None:
        header = PageHeader("Recommended For You", subtitle="Based on your library")
        self.add_to_content(header)
        self._grid = MediaGridView(self, parent=self.container)
        self.add_to_content(self._grid, stretch=1)
        items = data.fetch_recommendations(self.context.services, self._reference)
        self._exclude_self(items)
        if not items:
            self.show_empty()
            return
        self.show_content()
        self._grid.set_entities(items)

    def _exclude_self(self, items) -> None:
        if self._reference is None:
            return
        key = self._reference.key()
        items[:] = [i for i in items if i.key() != key]

    def refresh_theme(self) -> None:
        self._grid.refresh_artwork()


def _ref_from_row(services, row):
    from ui.models import EntityRef

    kind = str(row["media_type"])
    mid = int(row["media_id"])
    if kind == "movie":
        for r in services.search.search_movies("", limit=100000):
            if r.entity_id == mid:
                return EntityRef(kind=kind, entity_id=mid, title=r.title,
                                 year=r.year, artwork_kind="poster")
    elif kind == "tv":
        for r in services.search.search_tv_shows("", limit=100000):
            if r.entity_id == mid:
                return EntityRef(kind=kind, entity_id=mid, title=r.title,
                                 year=r.year, artwork_kind="poster")
    return None


def _ref_from_entry(services, entry):
    from ui.models import EntityRef

    if entry.entity_type == "movie":
        for r in services.search.search_movies("", limit=100000):
            if r.entity_id == entry.entity_id:
                return EntityRef(kind="movie", entity_id=entry.entity_id,
                                 title=r.title, year=r.year, artwork_kind="poster")
    elif entry.entity_type == "tv":
        for r in services.search.search_tv_shows("", limit=100000):
            if r.entity_id == entry.entity_id:
                return EntityRef(kind="tv", entity_id=entry.entity_id,
                                 title=r.title, year=r.year, artwork_kind="poster")
    return None
