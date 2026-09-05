"""TV Time — episode hierarchy view for TV shows.

Shows seasons and episodes with real data from the library.
Episode-level playback tracking is not supported by the frozen schema,
so this screen focuses on hierarchy and file availability.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.themes.tokens import Spacing, Typography


class TvTimeScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)

    def empty_title(self) -> str:
        return "No TV Shows Yet"

    def empty_subtitle(self) -> str:
        return "TV shows you add to your library will appear here."

    def page_title(self) -> str:
        return "TV Time"

    def load(self) -> None:
        self.start_async_load(self._gather)

    def _gather(self, services):
        from app.bootstrap import _initialized_connection
        from app.metadata.repository import MetadataRepository

        conn = _initialized_connection()
        repo = MetadataRepository(conn)

        # Get all TV shows
        tv_shows = data.fetch_tv_shows(services)
        result = []
        for show in tv_shows:
            seasons = repo.list_seasons(show.entity_id)
            show_data = {
                "id": show.entity_id,
                "title": show.title,
                "year": show.year,
                "seasons": [],
            }
            for season in seasons:
                episodes = repo.list_episodes(season["id"])
                season_data = {
                    "id": season["id"],
                    "season_number": season["season_number"],
                    "episode_count": len(episodes),
                    "episodes": episodes,
                }
                show_data["seasons"].append(season_data)
            result.append(show_data)
        return result

    def handle_data(self, payload) -> None:
        self.clear_content()
        shows = payload
        if not shows:
            self.show_empty()
            return
        self.add_to_content(PageHeader("TV Time", subtitle=f"{len(shows)} show(s)"))
        for show in shows:
            self._show_card(show)
        self.show_content()

    def _show_card(self, show: dict) -> None:
        card = QFrame()
        card.setObjectName("CardFrame")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(Spacing.L, Spacing.L, Spacing.L, Spacing.L)
        lay.setSpacing(Spacing.M)

        # Show title
        title = QLabel(show["title"])
        title.setStyleSheet(
            f"font-size: {Typography.SECTION_PX}px; font-weight: 700; "
            "background: transparent;"
        )
        lay.addWidget(title)

        if show["year"]:
            year_label = QLabel(str(show["year"]))
            year_label.setObjectName("SecondaryLabel")
            year_label.setStyleSheet(
                f"font-size: {Typography.METADATA_PX}px; background: transparent;"
            )
            lay.addWidget(year_label)

        # Seasons
        for season in show["seasons"]:
            season_widget = QWidget()
            season_lay = QHBoxLayout(season_widget)
            season_lay.setContentsMargins(Spacing.M, Spacing.S, Spacing.M, Spacing.S)

            season_label = QLabel(f"Season {season['season_number']}")
            season_label.setStyleSheet(
                f"font-size: {Typography.CARD_PX}px; font-weight: 600; "
                "background: transparent;"
            )
            ep_count = QLabel(f"{season['episode_count']} episodes")
            ep_count.setObjectName("SecondaryLabel")
            ep_count.setStyleSheet(
                f"font-size: {Typography.METADATA_PX}px; background: transparent;"
            )
            season_lay.addWidget(season_label)
            season_lay.addStretch(1)
            season_lay.addWidget(ep_count)
            lay.addWidget(season_widget)

            # Episodes
            for ep in season["episodes"]:
                ep_widget = QWidget()
                ep_lay = QHBoxLayout(ep_widget)
                ep_lay.setContentsMargins(Spacing.XL, 2, Spacing.M, 2)

                ep_num = QLabel(f"E{ep['episode_number']:02d}")
                ep_num.setFixedWidth(40)
                ep_num.setStyleSheet(
                    f"font-size: {Typography.METADATA_PX}px; "
                    "background: transparent;"
                )
                ep_title = QLabel(ep.get("title") or f"Episode {ep['episode_number']}")
                ep_title.setStyleSheet(
                    f"font-size: {Typography.METADATA_PX}px; "
                    "background: transparent;"
                )
                ep_lay.addWidget(ep_num)
                ep_lay.addWidget(ep_title)
                ep_lay.addStretch(1)
                lay.addWidget(ep_widget)

        lay.addStretch(1)
        self.add_to_content(card)

    def refresh_theme(self) -> None:
        pass
