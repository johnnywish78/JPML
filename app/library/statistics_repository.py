from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LibraryStats:
    total_movies: int
    total_tv_shows: int
    total_seasons: int
    total_episodes: int
    total_people: int
    total_artists: int
    total_albums: int
    total_tracks: int
    total_media_files: int
    missing_media_files: int


@dataclass(frozen=True, slots=True)
class PlaybackSummary:
    total_items: int
    completed: int
    in_progress: int
    total_watch_time_seconds: float


@dataclass(frozen=True, slots=True)
class GenreStat:
    name: str
    movie_count: int
    tv_count: int


@dataclass(frozen=True, slots=True)
class MediaBreakdown:
    movies_with_files: int
    shows_with_episodes: int
    tracks_with_files: int
    total_linked_files: int


class StatisticsRepository:
    """Read-only aggregate queries over existing JPML data.

    No dedicated statistics tables are needed; everything is derived from the
    library and playback tables deterministically.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def _count(self, table: str) -> int:
        row = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        return int(row[0])

    def library_stats(self) -> LibraryStats:
        missing = self._conn.execute(
            "SELECT COUNT(*) FROM media_files WHERE is_missing = 1"
        ).fetchone()
        return LibraryStats(
            total_movies=self._count("movies"),
            total_tv_shows=self._count("tv_shows"),
            total_seasons=self._count("seasons"),
            total_episodes=self._count("episodes"),
            total_people=self._count("people"),
            total_artists=self._count("artists"),
            total_albums=self._count("albums"),
            total_tracks=self._count("music_tracks"),
            total_media_files=self._count("media_files"),
            missing_media_files=int(missing[0]),
        )

    def playback_summary(self) -> PlaybackSummary:
        row = self._conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END), 0) AS completed,
                COALESCE(SUM(CASE WHEN completed = 0 AND last_position > 0 THEN 1 ELSE 0 END), 0) AS in_progress,
                COALESCE(SUM(CASE WHEN completed = 1 THEN duration ELSE 0 END), 0.0)
                  + COALESCE(SUM(CASE WHEN completed = 0 THEN last_position ELSE 0 END), 0.0)
                  AS watch_time
            FROM playback_history
            """
        ).fetchone()
        return PlaybackSummary(
            total_items=int(row["total"]),
            completed=int(row["completed"]),
            in_progress=int(row["in_progress"]),
            total_watch_time_seconds=float(row["watch_time"]),
        )

    def recent_playback(self, limit: int = 20) -> list[dict[str, object]]:
        limit = max(0, int(limit))
        rows = self._conn.execute(
            """
            SELECT
                ph.id, ph.media_type, ph.media_id, ph.file_path,
                ph.started_at, ph.stopped_at, ph.last_position,
                ph.duration, ph.completed,
                COALESCE(m.title, s.title, e.title, '') AS title
            FROM playback_history AS ph
            LEFT JOIN movies AS m ON ph.media_type = 'movie' AND m.id = ph.media_id
            LEFT JOIN tv_shows AS s ON ph.media_type = 'tv' AND s.id = ph.media_id
            LEFT JOIN episodes AS e ON ph.media_type = 'episode' AND e.id = ph.media_id
            ORDER BY COALESCE(ph.stopped_at, ph.started_at) DESC, ph.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def most_watched(self, limit: int = 20) -> list[dict[str, object]]:
        limit = max(0, int(limit))
        rows = self._conn.execute(
            """
            SELECT
                ph.media_type, ph.media_id,
                COALESCE(m.title, s.title, e.title, '') AS title,
                COUNT(*) AS plays,
                MAX(COALESCE(ph.stopped_at, ph.started_at)) AS last_played
            FROM playback_history AS ph
            LEFT JOIN movies AS m ON ph.media_type = 'movie' AND m.id = ph.media_id
            LEFT JOIN tv_shows AS s ON ph.media_type = 'tv' AND s.id = ph.media_id
            LEFT JOIN episodes AS e ON ph.media_type = 'episode' AND e.id = ph.media_id
            GROUP BY ph.media_type, ph.media_id
            ORDER BY plays DESC, last_played DESC, ph.media_type, ph.media_id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def genre_stats(self) -> list[GenreStat]:
        rows = self._conn.execute(
            """
            SELECT
                g.name,
                (SELECT COUNT(*) FROM movie_genres AS mg WHERE mg.genre_id = g.id) AS movie_count,
                (SELECT COUNT(*) FROM tv_genres AS tg WHERE tg.genre_id = g.id) AS tv_count
            FROM genres AS g
            ORDER BY g.name
            """
        ).fetchall()
        return [
            GenreStat(
                name=row["name"],
                movie_count=int(row["movie_count"]),
                tv_count=int(row["tv_count"]),
            )
            for row in rows
        ]

    def media_breakdown(self) -> MediaBreakdown:
        movies_with_files = self._conn.execute(
            "SELECT COUNT(DISTINCT movie_id) FROM movie_files"
        ).fetchone()[0]
        shows_with_episodes = self._conn.execute(
            "SELECT COUNT(DISTINCT episode_id) FROM episode_files"
        ).fetchone()[0]
        tracks_with_files = self._conn.execute(
            "SELECT COUNT(DISTINCT track_id) FROM track_files"
        ).fetchone()[0]
        total_linked = self._conn.execute(
            """
            SELECT (SELECT COUNT(*) FROM movie_files)
                 + (SELECT COUNT(*) FROM episode_files)
                 + (SELECT COUNT(*) FROM track_files) AS n
            """
        ).fetchone()[0]
        return MediaBreakdown(
            movies_with_files=int(movies_with_files),
            shows_with_episodes=int(shows_with_episodes),
            tracks_with_files=int(tracks_with_files),
            total_linked_files=int(total_linked),
        )
