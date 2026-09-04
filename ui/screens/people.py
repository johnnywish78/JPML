"""People — portrait grid with biography (when present)."""
from __future__ import annotations

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.cards.person_card import PersonCard
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_grid import MediaGridView


class PeopleScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)

    def empty_title(self) -> str:
        return "No People Yet"

    def empty_subtitle(self) -> str:
        return "People appear here as metadata is added to your movies "
        "and shows."

    def page_title(self) -> str:
        return "People"

    def load(self) -> None:
        header = PageHeader("People", subtitle="{n} people")
        self.add_to_content(header)
        self._header = header
        self._grid = MediaGridView(
            self, parent=self.container, card_cls=PersonCard, card_width=150
        )
        self.add_to_content(self._grid, stretch=1)
        self.start_async_load(lambda s: (data.fetch_people(s),))

    def handle_data(self, payload) -> None:
        people = payload[0]
        self._header.set_count(len(people))
        if not people:
            self.show_empty()
            return
        self.show_content()
        self._grid.set_entities(people)

    def refresh_theme(self) -> None:
        self._grid.refresh_artwork()
