from __future__ import annotations

import sqlite3

import pytest

from app.database.schema import initialize
from app.metadata.service import MetadataService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


def _repository(connection: sqlite3.Connection):
    from app.metadata.repository import MetadataRepository

    return MetadataRepository(connection)


def test_service_can_create_movie_from_identification() -> None:
    from app.metadata.identifier import IdentificationResult

    connection = _connection()
    service = MetadataService(_repository(connection))

    result = IdentificationResult(
        media_type="movie",
        title="Inception",
        year=2010,
        provider="imdb",
        external_id="tt1375666",
        confidence=1.0,
    )

    resolved = service.resolve_identification(result)

    assert resolved.entity_type == "movie"
    assert resolved.entity_id > 0
    assert resolved.created is True

    movie = connection.execute(
        "SELECT title, year FROM movies WHERE id = ?",
        (resolved.entity_id,),
    ).fetchone()

    assert movie["title"] == "Inception"
    assert movie["year"] == 2010


def test_service_does_not_duplicate_existing_external_id() -> None:
    from app.metadata.identifier import IdentificationResult

    connection = _connection()
    repository = _repository(connection)
    service = MetadataService(repository)

    result = IdentificationResult(
        media_type="movie",
        title="Inception",
        year=2010,
        provider="imdb",
        external_id="tt1375666",
        confidence=1.0,
    )

    first = service.resolve_identification(result)
    second = service.resolve_identification(result)

    assert first.entity_id == second.entity_id
    assert first.created is True
    assert second.created is False

    count = connection.execute(
        "SELECT COUNT(*) FROM movies"
    ).fetchone()[0]

    assert count == 1


def test_service_can_create_tv_show() -> None:
    from app.metadata.identifier import IdentificationResult

    connection = _connection()
    service = MetadataService(_repository(connection))

    result = IdentificationResult(
        media_type="tv",
        title="Breaking Bad",
        year=2008,
        provider="imdb",
        external_id="tt0903747",
        confidence=1.0,
    )

    resolved = service.resolve_identification(result)

    assert resolved.entity_type == "tv"

    row = connection.execute(
        "SELECT title, year FROM tv_shows WHERE id = ?",
        (resolved.entity_id,),
    ).fetchone()

    assert row["title"] == "Breaking Bad"
    assert row["year"] == 2008


def test_service_persists_metadata_source() -> None:
    from app.metadata.identifier import IdentificationResult

    connection = _connection()
    repository = _repository(connection)
    service = MetadataService(repository)

    result = IdentificationResult(
        media_type="movie",
        title="Dune",
        year=2021,
        provider="imdb",
        external_id="tt1160419",
        confidence=1.0,
    )

    resolved = service.resolve_identification(result)

    service.save_metadata(
        entity_type="movie",
        entity_id=resolved.entity_id,
        provider="imdb",
        metadata={
            "title": "Dune",
            "year": 2021,
            "overview": "A science fiction epic.",
        },
        metadata_version="1",
    )

    row = connection.execute(
        """
        SELECT provider, metadata_version, user_override
        FROM metadata_sources
        WHERE entity_type = 'movie' AND entity_id = ?
        """,
        (resolved.entity_id,),
    ).fetchone()

    assert row["provider"] == "imdb"
    assert row["metadata_version"] == "1"
    assert row["user_override"] == 0


def test_service_rejects_unsupported_media_type() -> None:
    from app.metadata.identifier import IdentificationResult

    connection = _connection()
    service = MetadataService(_repository(connection))

    result = IdentificationResult(
        media_type="person",
        title="Someone",
        year=None,
        provider="imdb",
        external_id="nm0000001",
        confidence=1.0,
    )

    with pytest.raises(ValueError):
        service.resolve_identification(result)
