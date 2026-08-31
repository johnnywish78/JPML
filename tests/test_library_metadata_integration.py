from __future__ import annotations

import sqlite3

from app.database.schema import initialize
from app.metadata.identifier import IdentificationResult
from app.metadata.library_integration import LibraryMetadataIntegration
from app.metadata.provider import StaticMetadataProvider
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


def connection() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    initialize(db)
    return db


def test_library_identification_flows_into_metadata() -> None:
    db = connection()
    repo = MetadataRepository(db)

    provider = StaticMetadataProvider(
        {
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "A thief enters dreams.",
                "genres": ["Action", "Sci-Fi", "Thriller"],
                "external_id": "tt1375666",
                "metadata_version": "static-v1",
            }
        }
    )

    service = MetadataService(repo, provider)
    integration = LibraryMetadataIntegration(service)

    result = IdentificationResult(
        media_type="movie",
        title="Inception",
        year=2010,
        provider="imdb",
        external_id="tt1375666",
        confidence=1.0,
    )

    outcome = integration.process_identification(result)

    assert outcome.resolution.entity_type == "movie"
    assert outcome.resolution.created is True
    assert outcome.metadata_fetched is True

    movie = db.execute(
        """
        SELECT title, year, overview
        FROM movies
        WHERE id = ?
        """,
        (outcome.resolution.entity_id,),
    ).fetchone()

    assert movie is not None
    assert movie["title"] == "Inception"
    assert movie["year"] == 2010
    assert "thief enters dreams" in movie["overview"]


def test_library_identification_persists_external_id() -> None:
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

    integration = LibraryMetadataIntegration(
        MetadataService(repo, provider)
    )

    result = IdentificationResult(
        media_type="movie",
        title="Dune",
        year=2021,
        provider="imdb",
        external_id="tt1160419",
        confidence=1.0,
    )

    outcome = integration.process_identification(result)

    external = db.execute(
        """
        SELECT provider, external_id, is_primary
        FROM external_ids
        WHERE entity_type = 'movie'
          AND entity_id = ?
        """,
        (outcome.resolution.entity_id,),
    ).fetchone()

    assert external is not None
    assert external["provider"] == "imdb"
    assert external["external_id"] == "tt1160419"
    assert external["is_primary"] == 1


def test_library_identification_persists_genres() -> None:
    db = connection()
    repo = MetadataRepository(db)

    provider = StaticMetadataProvider(
        {
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "A thief enters dreams.",
                "genres": ["Action", "Sci-Fi", "Thriller"],
                "external_id": "tt1375666",
                "metadata_version": "static-v1",
            }
        }
    )

    integration = LibraryMetadataIntegration(
        MetadataService(repo, provider)
    )

    result = IdentificationResult(
        media_type="movie",
        title="Inception",
        year=2010,
        provider="imdb",
        external_id="tt1375666",
        confidence=1.0,
    )

    outcome = integration.process_identification(result)

    rows = db.execute(
        """
        SELECT g.name
        FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.id
        WHERE mg.movie_id = ?
        ORDER BY g.name
        """,
        (outcome.resolution.entity_id,),
    ).fetchall()

    assert [row["name"] for row in rows] == [
        "Action",
        "Sci-Fi",
        "Thriller",
    ]


def test_library_identification_without_external_id_still_resolves() -> None:
    db = connection()
    repo = MetadataRepository(db)

    provider = StaticMetadataProvider({})
    integration = LibraryMetadataIntegration(
        MetadataService(repo, provider)
    )

    result = IdentificationResult(
        media_type="movie",
        title="Local Movie",
        year=2020,
        confidence=0.8,
    )

    outcome = integration.process_identification(result)

    assert outcome.resolution.entity_type == "movie"
    assert outcome.resolution.created is True
    assert outcome.metadata_fetched is False
