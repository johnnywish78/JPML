from __future__ import annotations

import sqlite3

import pytest

from app.database.schema import initialize
from app.library.watchlist_repository import WatchlistRepository
from app.services.watchlist import WatchlistService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


class TestWatchlistRepository:
    def test_add_list_remove(self) -> None:
        conn = _connection()
        repo = WatchlistRepository(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'A')")
        conn.execute("INSERT INTO tv_shows(id, title) VALUES (2, 'B')")
        conn.execute(
            "INSERT INTO seasons(id, tv_show_id, season_number) VALUES (1, 2, 1)"
        )
        conn.execute("INSERT INTO episodes(id, season_id, episode_number, title) "
                     "VALUES (3, 1, 1, 'E')")
        conn.commit()

        repo.add("movie", 1)
        repo.add("tv", 2)
        repo.add("episode", 3)
        assert repo.is_in_watchlist("movie", 1) is True
        assert len(repo.list()) == 3

        assert repo.remove("tv", 2) is True
        assert repo.is_in_watchlist("tv", 2) is False
        assert repo.remove("tv", 2) is False

    def test_duplicate_safe(self) -> None:
        conn = _connection()
        repo = WatchlistRepository(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'A')")
        conn.commit()
        repo.add("movie", 1)
        repo.add("movie", 1)
        count = conn.execute(
            "SELECT COUNT(*) FROM watchlist WHERE entity_type = 'movie'"
        ).fetchone()[0]
        assert count == 1

    def test_independent_from_favorites(self) -> None:
        conn = _connection()
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'A')")
        conn.commit()
        conn.execute("INSERT INTO favorites(entity_type, entity_id) VALUES ('movie', 1)")
        conn.commit()

        repo = WatchlistRepository(conn)
        assert repo.is_in_watchlist("movie", 1) is False
        from app.library.favorites_repository import FavoritesRepository

        assert FavoritesRepository(conn).is_favorite("movie", 1) is True

    def test_list_filtered_by_type(self) -> None:
        conn = _connection()
        repo = WatchlistRepository(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'A')")
        conn.execute("INSERT INTO tv_shows(id, title) VALUES (2, 'B')")
        conn.commit()
        repo.add("movie", 1)
        repo.add("tv", 2)
        movies = repo.list("movie")
        assert len(movies) == 1
        assert movies[0].entity_type == "movie"

    def test_prune_invalid(self) -> None:
        conn = _connection()
        repo = WatchlistRepository(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Keep')")
        conn.execute("INSERT INTO movies(id, title) VALUES (2, 'Gone')")
        conn.commit()
        repo.add("movie", 1)
        repo.add("movie", 2)
        conn.execute("DELETE FROM movies WHERE id = 2")
        conn.commit()
        removed = repo.prune_invalid()
        assert removed >= 1
        assert repo.is_in_watchlist("movie", 1) is True
        assert repo.is_in_watchlist("movie", 2) is False


class TestWatchlistService:
    def test_service_rejects_missing_entity(self) -> None:
        conn = _connection()
        svc = WatchlistService(WatchlistRepository(conn))
        with pytest.raises(LookupError):
            svc.add("episode", 999)

    def test_service_roundtrip_music_entity(self) -> None:
        conn = _connection()
        conn.execute(
            "INSERT INTO artists(id, name) VALUES (1, 'A')"
        )
        conn.execute(
            "INSERT INTO albums(id, artist_id, title) VALUES (1, 1, 'B')",
        )
        conn.execute(
            "INSERT INTO music_tracks(id, album_id, title) VALUES (1, 1, 'T')"
        )
        conn.commit()
        svc = WatchlistService(WatchlistRepository(conn))
        svc.add("track", 1)
        assert svc.is_in_watchlist("track", 1) is True
        entries = svc.list("track")
        assert len(entries) == 1
        assert svc.remove("track", 1) is True
