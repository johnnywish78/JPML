from __future__ import annotations

from app.library.statistics_repository import (
    GenreStat,
    LibraryStats,
    MediaBreakdown,
    PlaybackSummary,
    StatisticsRepository,
)


class StatisticsService:
    """UI-facing read-only statistics over the library and playback data.

    Values are computed deterministically from existing tables; nothing is
    cached or pre-computed.
    """

    def __init__(self, repository: StatisticsRepository) -> None:
        self._repo = repository

    @property
    def repository(self) -> StatisticsRepository:
        return self._repo

    def library(self) -> LibraryStats:
        return self._repo.library_stats()

    def playback(self) -> PlaybackSummary:
        return self._repo.playback_summary()

    def recent_playback(self, limit: int = 20) -> list[dict[str, object]]:
        return self._repo.recent_playback(limit)

    def most_watched(self, limit: int = 20) -> list[dict[str, object]]:
        return self._repo.most_watched(limit)

    def genres(self) -> list[GenreStat]:
        return self._repo.genre_stats()

    def media_breakdown(self) -> MediaBreakdown:
        return self._repo.media_breakdown()
