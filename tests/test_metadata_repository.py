from __future__ import annotations

import sqlite3

import pytest

from app.database.schema import initialize
from app.metadata.repository import MetadataRepository


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


def _movie_id(connection: sqlite3.Connection, title: str = "Test Movie") -> int:
    cursor = connection.execute(
        "INSERT INTO movies(title) VALUES (?)",
        (title,),
    )
    connection.commit()
    return int(cursor.lastrowid)


def _tv_id(connection: sqlite3.Connection, title: str = "Test Show") -> int:
    cursor = connection.execute(
        "INSERT INTO tv_shows(title) VALUES (?)",
        (title,),
    )
    connection.commit()
    return int(cursor.lastrowid)


def test_external_id_round_trip() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    row_id = repository.add_external_id(
        "movie",
        movie_id,
        "tmdb",
        "12345",
        is_primary=True,
    )

    assert row_id > 0
    assert repository.get_external_id("movie", movie_id, "tmdb") == "12345"
    assert repository.list_external_ids("movie", movie_id) == [
        {
            "provider": "tmdb",
            "external_id": "12345",
            "is_primary": True,
        }
    ]


def test_external_id_upsert_updates_existing_mapping() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    first_id = repository.upsert_external_id(
        "movie",
        movie_id,
        "imdb",
        "tt001",
    )
    second_id = repository.upsert_external_id(
        "movie",
        movie_id,
        "imdb",
        "tt002",
        is_primary=True,
    )

    assert first_id == second_id
    assert repository.get_external_id("movie", movie_id, "imdb") == "tt002"


def test_artwork_round_trip() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    repository.add_artwork(
        "movie",
        movie_id,
        "poster",
        provider="tmdb",
        provider_path="/abc",
        local_path="/cache/poster.jpg",
        width=500,
        height=750,
    )

    assert repository.list_artwork("movie", movie_id) == [
        {
            "artwork_type": "poster",
            "provider": "tmdb",
            "provider_path": "/abc",
            "local_path": "/cache/poster.jpg",
            "width": 500,
            "height": 750,
        }
    ]


def test_artwork_allows_same_type_from_different_providers() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    repository.add_artwork(
        "movie",
        movie_id,
        "poster",
        provider="tmdb",
    )
    repository.add_artwork(
        "movie",
        movie_id,
        "poster",
        provider="imdb",
    )

    assert len(repository.list_artwork("movie", movie_id)) == 2


def test_metadata_source_round_trip() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    repository.add_metadata_source(
        "movie",
        movie_id,
        "tmdb",
        fetched_at="2026-08-30T10:00:00",
        expires_at="2026-09-30T10:00:00",
        metadata_version="v1",
        user_override=True,
    )

    assert repository.get_metadata_source(
        "movie",
        movie_id,
        "tmdb",
    ) == {
        "provider": "tmdb",
        "fetched_at": "2026-08-30T10:00:00",
        "expires_at": "2026-09-30T10:00:00",
        "metadata_version": "v1",
        "user_override": True,
    }


def test_metadata_source_upsert_updates_existing_source() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    first_id = repository.upsert_metadata_source(
        "movie",
        movie_id,
        "tmdb",
        metadata_version="v1",
    )
    second_id = repository.upsert_metadata_source(
        "movie",
        movie_id,
        "tmdb",
        metadata_version="v2",
        user_override=True,
    )

    assert first_id == second_id
    source = repository.get_metadata_source(
        "movie",
        movie_id,
        "tmdb",
    )
    assert source is not None
    assert source["metadata_version"] == "v2"
    assert source["user_override"] is True


def test_movie_genres_are_set_and_replaced() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    repository.set_movie_genres(
        movie_id,
        ["Action", "Drama", "Action"],
    )
    assert repository.get_movie_genres(movie_id) == ["Action", "Drama"]

    repository.set_movie_genres(
        movie_id,
        ["Comedy"],
    )
    assert repository.get_movie_genres(movie_id) == ["Comedy"]


def test_tv_genres_are_set_and_replaced() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    tv_id = _tv_id(connection)

    repository.set_tv_genres(
        tv_id,
        ["Drama", "Sci-Fi"],
    )
    assert repository.get_tv_genres(tv_id) == ["Drama", "Sci-Fi"]

    repository.set_tv_genres(
        tv_id,
        [],
    )
    assert repository.get_tv_genres(tv_id) == []


def test_genre_names_are_shared_between_entities() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection, "Movie")
    tv_id = _tv_id(connection, "Show")

    repository.set_movie_genres(movie_id, ["Drama"])
    repository.set_tv_genres(tv_id, ["Drama"])

    count = connection.execute(
        "SELECT COUNT(*) FROM genres WHERE name = 'Drama'"
    ).fetchone()[0]

    assert count == 1


def test_empty_genre_name_is_rejected() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)

    with pytest.raises(ValueError):
        repository.get_or_create_genre("   ")


# ── Additional artwork tests ──────────────────────────────────────────────────

def test_artwork_for_tv_show() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    tv_id = _tv_id(connection)

    repository.add_artwork(
        "tv_show",
        tv_id,
        "poster",
        provider="tmdb",
        provider_path="/tv/123/poster.jpg",
        local_path="/cache/tv_poster.jpg",
        width=300,
        height=450,
    )

    artwork = repository.list_artwork("tv_show", tv_id)
    assert len(artwork) == 1
    assert artwork[0]["provider"] == "tmdb"
    assert artwork[0]["width"] == 300
    assert artwork[0]["height"] == 450


def test_list_artwork_empty() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)

    assert repository.list_artwork("movie", 9999) == []


def test_artwork_filtered_by_entity_type() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)
    tv_id = _tv_id(connection)

    repository.add_artwork("movie", movie_id, "poster", provider="tmdb")
    repository.add_artwork("tv_show", tv_id, "poster", provider="tmdb")

    assert len(repository.list_artwork("movie", movie_id)) == 1
    assert len(repository.list_artwork("tv_show", tv_id)) == 1


def test_artwork_null_dimensions() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    repository.add_artwork(
        "movie",
        movie_id,
        "poster",
        provider="tmdb",
        provider_path="/abc",
    )

    artwork = repository.list_artwork("movie", movie_id)
    assert len(artwork) == 1
    assert artwork[0]["width"] is None
    assert artwork[0]["height"] is None


def test_artwork_delete_with_entity_cascade() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    movie_id = _movie_id(connection)

    repository.add_artwork("movie", movie_id, "poster", provider="tmdb")
    repository.add_artwork("movie", movie_id, "fanart", provider="tmdb")
    assert len(repository.list_artwork("movie", movie_id)) == 2

    connection.execute(
        "DELETE FROM artwork WHERE entity_type = 'movie' AND entity_id = ?",
        (movie_id,),
    )
    connection.commit()

    assert repository.list_artwork("movie", movie_id) == []
