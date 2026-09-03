from __future__ import annotations

import sqlite3

from app.database.schema import initialize
from app.library.search import SearchRepository
from app.services.search import SearchService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO movies(id, title, year) VALUES (1, 'Inception', 2010)")
    conn.execute("INSERT INTO movies(id, title, year) VALUES (2, 'Inception Revisited', 2020)")
    conn.execute("INSERT INTO movies(id, title, year) VALUES (3, 'Interstellar', 2014)")
    conn.execute("INSERT INTO tv_shows(id, title, year) VALUES (1, 'Breaking Bad', 2008)")
    conn.execute("INSERT INTO people(id, name) VALUES (1, 'Christopher Nolan')")
    conn.execute("INSERT INTO people(id, name) VALUES (2, 'Christina Aguilera')")
    conn.execute("INSERT INTO artists(id, name) VALUES (1, 'Daft Punk')")
    conn.execute(
        "INSERT INTO albums(id, artist_id, title) VALUES (1, 1, 'Random Access Memories')"
    )
    conn.execute(
        "INSERT INTO music_tracks(id, album_id, title) VALUES (1, 1, 'Get Lucky')"
    )
    conn.execute(
        "INSERT INTO music_tracks(id, album_id, title) VALUES (2, 1, 'Instant Crush')"
    )
    conn.commit()


class TestSearchRepositoryMusic:
    def test_search_artists(self) -> None:
        conn = _connection()
        _seed(conn)
        repo = SearchRepository(conn)
        results = repo.search_artists("daft")
        assert len(results) == 1
        assert results[0].entity_type == "artist"
        assert results[0].title == "Daft Punk"

    def test_search_albums(self) -> None:
        conn = _connection()
        _seed(conn)
        repo = SearchRepository(conn)
        results = repo.search_albums("random")
        assert len(results) == 1
        assert results[0].entity_type == "album"
        assert results[0].year is None

    def test_search_tracks(self) -> None:
        conn = _connection()
        _seed(conn)
        repo = SearchRepository(conn)
        results = repo.search_tracks("crush")
        assert len(results) == 1
        assert results[0].entity_type == "track"
        assert results[0].title == "Instant Crush"

    def test_search_people(self) -> None:
        conn = _connection()
        _seed(conn)
        repo = SearchRepository(conn)
        results = repo.search_people("christ")
        assert {r.title for r in results} == {
            "Christopher Nolan",
            "Christina Aguilera",
        }
        assert all(r.entity_type == "person" for r in results)

    def test_movie_search_exact_match_first(self) -> None:
        conn = _connection()
        _seed(conn)
        repo = SearchRepository(conn)
        results = repo.search_movies("inception")
        assert results[0].title == "Inception"
        assert results[1].title == "Inception Revisited"


class TestSearchService:
    def _service(self, conn: sqlite3.Connection) -> SearchService:
        return SearchService(SearchRepository(conn))

    def test_search_music_combines_entities(self) -> None:
        conn = _connection()
        _seed(conn)
        svc = self._service(conn)
        results = svc.search_music("daft")
        assert {r.entity_type for r in results} == {"artist"}

        results = svc.search_music("random")
        assert {r.entity_type for r in results} == {"album"}

        results = svc.search_music("get")
        assert {r.entity_type for r in results} == {"track"}

    def test_search_all_unified(self) -> None:
        conn = _connection()
        _seed(conn)
        svc = self._service(conn)
        results = svc.search_all("inception")
        assert {r.entity_type for r in results} == {"movie"}
        assert len(results) == 2

        results = svc.search_all("daft")
        assert results[0].entity_type == "artist"

    def test_search_all_respects_limit(self) -> None:
        conn = _connection()
        _seed(conn)
        svc = self._service(conn)
        results = svc.search_all("", limit=5)
        assert len(results) <= 5
        # deterministic order: title, entity_type, entity_id
        keys = [(r.title, r.entity_type, r.entity_id) for r in results]
        assert keys == sorted(keys)

    def test_empty_query_returns_all_capped(self) -> None:
        conn = _connection()
        _seed(conn)
        svc = self._service(conn)
        results = svc.search_movies("", limit=100)
        assert len(results) == 3
