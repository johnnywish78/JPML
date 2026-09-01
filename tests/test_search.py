from __future__ import annotations

import sqlite3

import pytest

from app.database.schema import initialize
from app.metadata.repository import MetadataRepository
from app.library.search import SearchRepository, SearchResult


def _make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


@pytest.fixture()
def db():
    conn = _make_connection()
    yield conn
    conn.close()


@pytest.fixture()
def search_repo(db: sqlite3.Connection) -> SearchRepository:
    return SearchRepository(db)


@pytest.fixture()
def metadata_repo(db: sqlite3.Connection) -> MetadataRepository:
    return MetadataRepository(db)


class TestSearchMovies:
    def test_no_movies(self, search_repo: SearchRepository) -> None:
        assert search_repo.search_movies("foo") == []

    def test_finds_movie(self, search_repo: SearchRepository, metadata_repo: MetadataRepository) -> None:
        metadata_repo.create_movie(title="The Matrix", year=1999)
        results = search_repo.search_movies("Matrix")
        assert len(results) == 1
        assert results[0].title == "The Matrix"
        assert results[0].entity_type == "movie"
        assert results[0].year == 1999

    def test_case_insensitive(self, search_repo: SearchRepository, metadata_repo: MetadataRepository) -> None:
        metadata_repo.create_movie(title="The Matrix")
        assert len(search_repo.search_movies("matrix")) == 1
        assert len(search_repo.search_movies("MATRIX")) == 1
        assert len(search_repo.search_movies("Matrix")) == 1

    def test_exact_title_ranked_first(
        self, search_repo: SearchRepository, metadata_repo: MetadataRepository
    ) -> None:
        metadata_repo.create_movie(title="Inception")
        metadata_repo.create_movie(title="Inception 2: Electric Boogaloo")
        results = search_repo.search_movies("Inception")
        assert results[0].title == "Inception"

    def test_limit(self, search_repo: SearchRepository, metadata_repo: MetadataRepository) -> None:
        for i in range(10):
            metadata_repo.create_movie(title=f"Movie {i}")
        results = search_repo.search_movies("Movie", limit=5)
        assert len(results) == 5


class TestSearchTVShows:
    def test_finds_tv_show(self, search_repo: SearchRepository, metadata_repo: MetadataRepository) -> None:
        metadata_repo.create_tv_show(title="Breaking Bad", year=2008)
        results = search_repo.search_tv_shows("Breaking")
        assert len(results) == 1
        assert results[0].entity_type == "tv_show"
        assert results[0].title == "Breaking Bad"
        assert results[0].year == 2008

    def test_no_tv_shows(self, search_repo: SearchRepository) -> None:
        assert search_repo.search_tv_shows("foo") == []


class TestSearchAll:
    def test_combined_results(self, search_repo: SearchRepository, metadata_repo: MetadataRepository) -> None:
        metadata_repo.create_movie(title="Star Wars")
        metadata_repo.create_tv_show(title="Star Trek")
        results = search_repo.search_all("Star")
        types = {r.entity_type for r in results}
        assert "movie" in types
        assert "tv_show" in types

    def test_limit_applied(self, search_repo: SearchRepository, metadata_repo: MetadataRepository) -> None:
        for i in range(20):
            metadata_repo.create_movie(title=f"Movie {i}")
        results = search_repo.search_all("Movie", limit=5)
        assert len(results) == 5
