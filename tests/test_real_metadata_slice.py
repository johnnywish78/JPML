from __future__ import annotations

import sqlite3

from app.database.schema import initialize
from app.metadata.provider import StaticMetadataProvider
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


def connection() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    initialize(db)
    return db


def test_real_metadata_slice_persists_movie_metadata() -> None:
    db = connection()
    repo = MetadataRepository(db)

    provider = StaticMetadataProvider(
        {
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "A skilled extractor enters shared dreams.",
                "genres": ["Science Fiction", "Thriller"],
                "external_id": "tt1375666",
                "metadata_version": "static-v1",
            }
        }
    )

    service = MetadataService(repo, provider)

    movie_id = repo.create_movie(title="Inception", year=2010)

    assert service.fetch_and_save_metadata(
        entity_type="movie",
        entity_id=movie_id,
        external_id="tt1375666",
    )

    movie = db.execute(
        "SELECT title, year, overview FROM movies WHERE id = ?",
        (movie_id,),
    ).fetchone()

    assert movie is not None
    assert movie["title"] == "Inception"
    assert movie["year"] == 2010
    assert "shared dreams" in movie["overview"]

    source = repo.get_metadata_source(
        "movie",
        movie_id,
        "static",
    )

    assert source is not None
    assert source["metadata_version"] == "static-v1"


def test_real_metadata_slice_persists_genres() -> None:
    db = connection()
    repo = MetadataRepository(db)

    provider = StaticMetadataProvider(
        {
            "movie:tt1160419": {
                "title": "Dune",
                "year": 2021,
                "overview": "A noble family becomes involved in a galactic struggle.",
                "genres": ["Science Fiction", "Adventure", "Drama"],
                "external_id": "tt1160419",
                "metadata_version": "static-v1",
            }
        }
    )

    service = MetadataService(repo, provider)
    movie_id = repo.create_movie(title="Dune", year=2021)

    assert service.fetch_and_save_metadata(
        entity_type="movie",
        entity_id=movie_id,
        external_id="tt1160419",
    )

    rows = db.execute(
        """
        SELECT g.name
        FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.id
        WHERE mg.movie_id = ?
        ORDER BY g.name
        """,
        (movie_id,),
    ).fetchall()

    assert [row["name"] for row in rows] == [
        "Adventure",
        "Drama",
        "Science Fiction",
    ]


def test_missing_provider_metadata_does_not_modify_movie() -> None:
    db = connection()
    repo = MetadataRepository(db)

    provider = StaticMetadataProvider({})

    service = MetadataService(repo, provider)
    movie_id = repo.create_movie(title="Unknown", year=None)

    assert not service.fetch_and_save_metadata(
        entity_type="movie",
        entity_id=movie_id,
        external_id="tt0000000",
    )

    movie = db.execute(
        "SELECT title, year FROM movies WHERE id = ?",
        (movie_id,),
    ).fetchone()

    assert movie["title"] == "Unknown"
    assert movie["year"] is None
