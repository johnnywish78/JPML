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


def test_file_identification_to_metadata_persistence() -> None:
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

    identification = IdentificationResult(
        media_type="movie",
        title="Inception",
        year=2010,
        provider="imdb",
        external_id="tt1375666",
        confidence=1.0,
        path="/media/movies/Inception (2010).mkv",
        raw_title="Inception (2010)",
    )

    outcome = integration.process_identification(identification)

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
    assert movie["overview"] == "A thief enters dreams."

    genres = db.execute(
        """
        SELECT g.name
        FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.id
        WHERE mg.movie_id = ?
        ORDER BY g.name
        """,
        (outcome.resolution.entity_id,),
    ).fetchall()

    assert [row["name"] for row in genres] == [
        "Action",
        "Sci-Fi",
        "Thriller",
    ]

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
    assert external["external_id"] == "tt1375666"
    assert external["is_primary"] == 1
