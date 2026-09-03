from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.database.schema import initialize
from app.library.statistics_repository import StatisticsRepository
from app.services.statistics import StatisticsService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


def _now(offset_days: float = 0.0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=offset_days)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _seed(conn: sqlite3.Connection) -> dict[str, int]:
    # library
    conn.execute("INSERT INTO movies(id, title) VALUES (1, 'A')")
    conn.execute("INSERT INTO movies(id, title) VALUES (2, 'B')")
    conn.execute("INSERT INTO tv_shows(id, title) VALUES (1, 'S')")
    conn.execute(
        "INSERT INTO seasons(id, tv_show_id, season_number) VALUES (1, 1, 1)"
    )
    conn.execute(
        "INSERT INTO episodes(id, season_id, episode_number, title) "
        "VALUES (1, 1, 1, 'E1'), (2, 1, 2, 'E2')"
    )
    conn.execute("INSERT INTO people(id, name) VALUES (1, 'P')")
    conn.execute("INSERT INTO artists(id, name) VALUES (1, 'Artist')")
    conn.execute(
        "INSERT INTO albums(id, artist_id, title) VALUES (1, 1, 'Album')"
    )
    conn.execute(
        "INSERT INTO music_tracks(id, album_id, title) VALUES (1, 1, 'T1')"
    )
    # media files: linked movie file, missing file, unlinked file
    conn.execute(
        "INSERT INTO media_files(id, path, filename, is_missing) "
        "VALUES (1, '/a.mkv', 'a.mkv', 0)"
    )
    conn.execute(
        "INSERT INTO media_files(id, path, filename, is_missing) "
        "VALUES (2, '/gone.mkv', 'gone.mkv', 1)"
    )
    conn.execute(
        "INSERT INTO media_files(id, path, filename, is_missing) "
        "VALUES (3, '/free.mp3', 'free.mp3', 0)"
    )
    conn.execute(
        "INSERT INTO movie_files(movie_id, media_file_id) VALUES (1, 1)"
    )
    conn.execute(
        "INSERT INTO episode_files(episode_id, media_file_id) VALUES (1, 1)"
    )
    conn.execute(
        "INSERT INTO track_files(track_id, media_file_id) VALUES (1, 3)"
    )
    # genres
    conn.execute("INSERT INTO genres(id, name) VALUES (1, 'Action')")
    conn.execute("INSERT INTO genres(id, name) VALUES (2, 'Drama')")
    conn.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (1, 1)")
    conn.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (1, 2)")
    conn.execute("INSERT INTO tv_genres(tv_show_id, genre_id) VALUES (1, 1)")
    # playback: one completed, one in-progress
    conn.execute(
        """
        INSERT INTO playback_history(
            media_type, media_id, file_path, started_at, stopped_at,
            last_position, duration, completed
        ) VALUES ('movie', 1, '/a.mkv', ?, ?, 3600.0, 3600.0, 1)
        """,
        (_now(-2), _now(-2)),
    )
    conn.execute(
        """
        INSERT INTO playback_history(
            media_type, media_id, file_path, started_at, stopped_at,
            last_position, duration, completed
        ) VALUES ('episode', 1, '/a.mkv', ?, ?, 120.0, 3600.0, 0)
        """,
        (_now(-1), _now(-1)),
    )
    return {}


class TestStatisticsRepository:
    def test_library_stats(self) -> None:
        conn = _connection()
        _seed(conn)
        stats = StatisticsRepository(conn).library_stats()
        assert stats.total_movies == 2
        assert stats.total_tv_shows == 1
        assert stats.total_seasons == 1
        assert stats.total_episodes == 2
        assert stats.total_people == 1
        assert stats.total_artists == 1
        assert stats.total_albums == 1
        assert stats.total_tracks == 1
        assert stats.total_media_files == 3
        assert stats.missing_media_files == 1

    def test_playback_summary(self) -> None:
        conn = _connection()
        _seed(conn)
        summary = StatisticsRepository(conn).playback_summary()
        assert summary.total_items == 2
        assert summary.completed == 1
        assert summary.in_progress == 1
        assert summary.total_watch_time_seconds == 3600.0 + 120.0

    def test_recent_playback_ordering(self) -> None:
        conn = _connection()
        _seed(conn)
        recent = StatisticsRepository(conn).recent_playback()
        # episode played more recently comes first
        assert recent[0]["media_type"] == "episode"
        assert recent[1]["media_type"] == "movie"
        assert recent[1]["title"] == "A"
        assert len(StatisticsRepository(conn).recent_playback(limit=1)) == 1

    def test_most_watched(self) -> None:
        conn = _connection()
        _seed(conn)
        # add one more play of movie 1
        conn.execute(
            """
            INSERT INTO playback_history(
                media_type, media_id, file_path, started_at, last_position,
                duration, completed
            ) VALUES ('movie', 1, '/a.mkv', ?, 10.0, 3600.0, 0)
            """,
            (_now(0),),
        )
        conn.commit()
        most = StatisticsRepository(conn).most_watched()
        assert most[0]["media_type"] == "movie"
        assert most[0]["media_id"] == 1
        assert most[0]["plays"] == 2
        assert most[0]["title"] == "A"

    def test_genre_stats(self) -> None:
        conn = _connection()
        _seed(conn)
        genres = StatisticsRepository(conn).genre_stats()
        by_name = {g.name: g for g in genres}
        assert by_name["Action"].movie_count == 1
        assert by_name["Action"].tv_count == 1
        assert by_name["Drama"].movie_count == 1
        assert by_name["Drama"].tv_count == 0

    def test_media_breakdown(self) -> None:
        conn = _connection()
        _seed(conn)
        breakdown = StatisticsRepository(conn).media_breakdown()
        assert breakdown.movies_with_files == 1
        assert breakdown.shows_with_episodes == 1
        assert breakdown.tracks_with_files == 1
        assert breakdown.total_linked_files == 3


class TestStatisticsService:
    def test_service_delegates(self) -> None:
        conn = _connection()
        _seed(conn)
        svc = StatisticsService(StatisticsRepository(conn))
        assert svc.library().total_movies == 2
        assert svc.playback().completed == 1
        assert len(svc.recent_playback()) == 2
        assert svc.genres()[0].name in ("Action", "Drama")
        assert svc.media_breakdown().total_linked_files == 3

    def test_empty_library_zeroes(self) -> None:
        conn = _connection()
        svc = StatisticsService(StatisticsRepository(conn))
        stats = svc.library()
        assert stats.total_movies == 0
        assert stats.missing_media_files == 0
        summary = svc.playback()
        assert summary.total_items == 0
        assert summary.total_watch_time_seconds == 0.0
