"""Statistics — read-only, computed live. No fabricated numbers."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

import ui.app.data as data
from ui.app.screen_actions import ScreenActions
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.media_row import CardFactory, MediaRow, SectionHeader
from ui.themes.tokens import Radius, Spacing, Typography


def stat_tile(label: str, value: str, parent=None) -> QFrame:
    tile = QFrame(parent)
    tile.setObjectName("ElevatedFrame")
    layout = QVBoxLayout(tile)
    layout.setContentsMargins(Spacing.L, Spacing.L, Spacing.L, Spacing.L)
    layout.setSpacing(4)
    value_label = QLabel(value)
    value_label.setStyleSheet(
        f"font-size: 30px; font-weight: 700; background: transparent;"
    )
    title_label = QLabel(label)
    title_label.setObjectName("SecondaryLabel")
    title_label.setStyleSheet(
        f"font-size: {Typography.METADATA_PX}px; background: transparent;"
    )
    layout.addWidget(value_label)
    layout.addWidget(title_label)
    return tile


class StatisticsScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)

    def page_title(self) -> str:
        return "Statistics"

    def empty_title(self) -> str:
        return "No Data Yet"

    def empty_subtitle(self) -> str:
        return "Statistics appear once your library has media and "
        "playback history."

    def load(self) -> None:
        self.start_async_load(self._gather)

    def _gather(self, services):
        stats = services.statistics.library()
        playback = services.statistics.playback()
        breakdown = services.statistics.media_breakdown()
        most = services.statistics.most_watched(8)
        recent = services.statistics.recent_playback(8)
        genres = services.statistics.genres()
        movie_like = [g for g in genres if g.movie_count or g.tv_count]
        return (stats, playback, breakdown, most, recent, movie_like)

    def handle_data(self, payload) -> None:
        (stats, playback, breakdown, most, recent, genres) = payload
        total_media = stats.total_movies + stats.total_tv_shows + stats.total_tracks
        if total_media == 0 and playback.total_items == 0:
            self.show_empty()
            return
        self.clear_content()
        self.add_to_content(PageHeader("Statistics", subtitle="Library & playback, live"))

        grid = QGridLayout()
        grid.setSpacing(Spacing.M)
        grid.setContentsMargins(0, 0, 0, Spacing.L)
        tiles = [
            stat_tile("Movies", str(stats.total_movies)),
            stat_tile("TV Shows", str(stats.total_tv_shows)),
            stat_tile("Episodes", str(stats.total_episodes)),
            stat_tile("Music Tracks", str(stats.total_tracks)),
            stat_tile("Media Files", str(stats.total_media_files)),
            stat_tile("Missing Files", str(stats.missing_media_files)),
            stat_tile("Completed", str(playback.completed)),
            stat_tile("In Progress", str(playback.in_progress)),
        ]
        for index, tile in enumerate(tiles):
            grid.addWidget(tile, divmod(index, 4)[1], divmod(index, 4)[0])
        wrap = QWidget()
        wrap_layout = QVBoxLayout(wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addLayout(grid)
        self.add_to_content(wrap)

        watch_time = _fmt(playback.total_watch_time_seconds)
        self.add_to_content(
            _label_row(f"Total watch time: {watch_time}" if watch_time else "")
        )

        if most:
            self._section("Most Watched", most)
        if recent:
            self._section("Recently Played", recent)
        if genres:
            self._genre_rows(genres)
        self.show_content()

    def _section(self, title: str, rows) -> None:
        self.add_to_content(SectionHeader(title))
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for row in rows:
            name = str(row.get("title") or row.get("media_type"))
            meta = row.get("plays")
            when = row.get("last_played") or row.get("stopped_at")
            text = name
            if meta is not None:
                text += f"  ·  {meta} plays"
            if when:
                text += f"  ·  {when}"
            label_row = QWidget()
            ll = QHBoxLayout(label_row)
            ll.setContentsMargins(0, 6, 0, 6)
            lab = QLabel(text)
            lab.setStyleSheet(
                f"font-size: {Typography.CARD_PX}px; background: transparent;"
            )
            ll.addWidget(lab)
            ll.addStretch(1)
            layout.addWidget(label_row)
        self.add_to_content(container)

    def _genre_rows(self, genres) -> None:
        self.add_to_content(SectionHeader("Genres"))
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S)
        for g in genres:
            chip = QFrame()
            chip.setObjectName("CardFrame")
            cl = QHBoxLayout(chip)
            cl.setContentsMargins(10, 6, 10, 6)
            cl.setSpacing(6)
            name = QLabel(g.name)
            name.setStyleSheet(
                f"font-size: {Typography.METADATA_PX}px; background: transparent;"
            )
            count = QLabel(f"{g.movie_count + g.tv_count}")
            count.setObjectName("MutedLabel")
            count.setStyleSheet(
                f"font-size: {Typography.METADATA_PX}px; background: transparent;"
            )
            cl.addWidget(name)
            cl.addWidget(count)
            layout.addWidget(chip)
        layout.addStretch(1)
        self.add_to_content(container)

    def refresh_theme(self) -> None:
        pass


def _fmt(seconds: float) -> str:
    from ui.utils.formatting import format_duration_label

    return format_duration_label(seconds)


def _label_row(text: str) -> QWidget:
    label = QLabel(text) if text else QWidget()
    if text:
        label.setObjectName("SecondaryLabel")
        label.setStyleSheet(
            f"font-size: {Typography.METADATA_PX}px; background: transparent; "
            f"margin-bottom: 12px;"
        )
    return label
