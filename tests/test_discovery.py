from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from app.database.schema import initialize
from app.library.discovery_repository import DiscoveryRepository
from app.services.discovery import (
    DiscoveryService,
    LocalTrendingProvider,
    create_trending_provider,
)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


def _now(offset_days: float = 0.0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(days=offset_days)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _play(conn: sqlite3.Connection, media_type: str, media_id: int,
          offset_days: float, completed: int = 0) -> None:
    conn.execute(
        """
        INSERT INTO playback_history(
            media_type, media_id, file_path, started_at, last_position,
            duration, completed
        ) VALUES (?, ?, '/f.mkv', ?, ?, ?, ?)
        """,
        (
            media_type,
            media_id,
            _now(offset_days),
            30.0,
            3600.0,
            completed,
        ),
    )
    conn.commit()


class TestTrending:
    def test_recent_activity_ranked_by_plays(self) -> None:
        conn = _connection()
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Alpha')")
        conn.execute("INSERT INTO movies(id, title) VALUES (2, 'Beta')")
        conn.commit()
        _play(conn, "movie", 1, -1)
        _play(conn, "movie", 1, -2)
        _play(conn, "movie", 1, -3)
        _play(conn, "movie", 2, -1)

        repo = DiscoveryRepository(conn)
        items = repo.get_trending_recent(10)
        assert [i.entity_id for i in items] == [1, 2]
        assert items[0].plays == 3
        assert items[0].title == "Alpha"
        assert "3" in items[0].reason

    def test_old_activity_excluded(self) -> None:
        conn = _connection()
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Old')")
        conn.commit()
        _play(conn, "movie", 1, -60)

        repo = DiscoveryRepository(conn)
        assert repo.get_trending_recent(10) == []

    def test_fallback_to_newest_added(self) -> None:
        conn = _connection()
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Newish')")
        conn.execute("INSERT INTO tv_shows(id, title) VALUES (1, 'Newer')")
        conn.commit()

        repo = DiscoveryRepository(conn)
        items = repo.get_newest_added(10)
        assert len(items) == 2
        titles = {i.title for i in items}
        assert titles == {"Newish", "Newer"}
        assert all(i.plays == 0 for i in items)

    def test_provider_local_fallback(self) -> None:
        conn = _connection()
        repo = DiscoveryRepository(conn)
        provider = LocalTrendingProvider(repo)
        assert provider.name == "local"
        assert provider.get_trending(5) == []  # empty library, no playback

        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Only')")
        conn.commit()
        items = provider.get_trending(5)
        assert len(items) == 1
        assert items[0].title == "Only"

    def test_provider_factory(self) -> None:
        conn = _connection()
        repo = DiscoveryRepository(conn)
        assert create_trending_provider("local", repository=repo).name == "local"
        assert create_trending_provider(None, repository=repo).name == "local"
        with pytest.raises(ValueError):
            create_trending_provider("netflix", repository=repo)
        with pytest.raises(ValueError):
            create_trending_provider("local")  # missing repository


class TestRecommendations:
    def _setup_genres(self, conn: sqlite3.Connection) -> None:
        conn.execute("INSERT INTO genres(id, name) VALUES (1, 'Action')")
        conn.execute("INSERT INTO genres(id, name) VALUES (2, 'Sci-Fi')")
        conn.execute("INSERT INTO genres(id, name) VALUES (3, 'Drama')")
        conn.commit()

    def test_genre_overlap_ranking_with_favorite_boost(self) -> None:
        conn = _connection()
        self._setup_genres(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Ref')")
        conn.execute("INSERT INTO movies(id, title) VALUES (2, 'High')")
        conn.execute("INSERT INTO movies(id, title) VALUES (3, 'Low')")
        # Ref: Action + Sci-Fi
        conn.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (1, 1)")
        conn.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (1, 2)")
        # High: Action + Sci-Fi + Drama
        conn.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (2, 1)")
        conn.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (2, 2)")
        conn.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (2, 3)")
        # Low: Action
        conn.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (3, 1)")
        conn.commit()
        conn.execute(
            "INSERT INTO favorites(entity_type, entity_id) VALUES ('movie', 2)"
        )
        conn.commit()

        repo = DiscoveryRepository(conn)
        results = repo.genre_recommendations("movie", 1, 10)
        assert [r.entity_id for r in results] == [2, 3]
        assert results[0].score == 3  # 2 shared + favorite boost
        assert "favorites" in results[0].reason
        assert results[1].score == 1

    def test_excludes_self_and_unwatched_fallback(self) -> None:
        conn = _connection()
        self._setup_genres(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Ref')")
        conn.execute("INSERT INTO movies(id, title) VALUES (2, 'Fresh')")
        conn.execute("INSERT INTO movies(id, title) VALUES (3, 'Older')")
        conn.commit()
        # no genres on 'Ref'
        repo = DiscoveryRepository(conn)
        assert repo.genre_recommendations("movie", 1, 10) == []

        # fallback excludes the reference item itself
        fallback = repo.unwatched_recent("movie", 10, exclude_id=1)
        titles = [r.title for r in fallback]
        assert "Ref" not in titles
        assert set(titles) == {"Fresh", "Older"}

        # watched items are excluded as well
        _play(conn, "movie", 2, -1)
        fallback = repo.unwatched_recent("movie", 10, exclude_id=1)
        titles = [r.title for r in fallback]
        assert titles == ["Older"]

    def test_invalid_entity_type_raises(self) -> None:
        conn = _connection()
        repo = DiscoveryRepository(conn)
        with pytest.raises(ValueError):
            repo.genre_recommendations("track", 1, 5)
        with pytest.raises(ValueError):
            repo.unwatched_recent("track", 5)

    def test_recommendation_for_tv(self) -> None:
        conn = _connection()
        self._setup_genres(conn)
        conn.execute("INSERT INTO tv_shows(id, title) VALUES (1, 'RefShow')")
        conn.execute("INSERT INTO tv_shows(id, title) VALUES (2, 'Other')")
        conn.execute("INSERT INTO tv_genres(tv_show_id, genre_id) VALUES (1, 1)")
        conn.execute("INSERT INTO tv_genres(tv_show_id, genre_id) VALUES (2, 1)")
        conn.commit()

        repo = DiscoveryRepository(conn)
        results = repo.genre_recommendations("tv", 1, 5)
        assert len(results) == 1
        assert results[0].entity_type == "tv"
        assert results[0].score == 1


class TestDiscoveryService:
    def test_trending_and_discover(self) -> None:
        conn = _connection()
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Hit')")
        conn.commit()
        _play(conn, "movie", 1, -1)
        _play(conn, "movie", 1, -1)

        repo = DiscoveryRepository(conn)
        svc = DiscoveryService(repo)
        trending = svc.trending(5)
        assert len(trending) == 1
        assert trending[0].title == "Hit"
        assert svc.discover(5) == trending

    def test_recommendations_uses_fallback(self) -> None:
        conn = _connection()
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Ref')")
        conn.execute("INSERT INTO movies(id, title) VALUES (2, 'New')")
        conn.commit()
        repo = DiscoveryRepository(conn)
        svc = DiscoveryService(repo)
        # 'Ref' has no genres and 'New' is unwatched -> fallback lists 'New'
        recs = svc.recommendations("movie", 1, 5)
        assert [r.title for r in recs] == ["New"]
        assert recs[0].score == 0

    def test_service_custom_provider(self) -> None:
        from app.library.discovery_repository import TrendingItem

        class FixedProvider(LocalTrendingProvider):
            name = "fixed"

            def get_trending(self, limit: int = 10) -> list[TrendingItem]:
                return [
                    TrendingItem(
                        entity_type="movie",
                        entity_id=1,
                        title="Curated",
                        plays=0,
                        reason="curated feed",
                    )
                ]

        conn = _connection()
        repo = DiscoveryRepository(conn)
        svc = DiscoveryService(repo, trending_provider=FixedProvider(repo))
        items = svc.trending(5)
        assert items[0].title == "Curated"
        assert svc.trending_provider.name == "fixed"
