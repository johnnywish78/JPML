from __future__ import annotations

import sqlite3

import pytest

from app.database.schema import initialize
from app.metadata.provider import ProviderMetadata, StaticMetadataProvider
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize(connection)
    return connection


def test_service_can_use_injected_provider() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)

    provider = StaticMetadataProvider(
        {
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "A dream within a dream.",
                "genres": ["Sci-Fi", "Thriller"],
                "external_id": "tt1375666",
                "metadata_version": "v1",
            }
        }
    )

    service = MetadataService(repository, provider)

    movie_id = repository.create_movie(title="Inception", year=2010)

    assert service.fetch_and_save_metadata(
        entity_type="movie",
        entity_id=movie_id,
        external_id="tt1375666",
    ) is True

    row = connection.execute(
        "SELECT title, year, overview FROM movies WHERE id = ?",
        (movie_id,),
    ).fetchone()

    assert row == (
        "Inception",
        2010,
        "A dream within a dream.",
    )


def test_service_returns_false_when_provider_has_no_record() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    provider = StaticMetadataProvider({})

    service = MetadataService(repository, provider)
    movie_id = repository.create_movie(title="Unknown", year=None)

    assert service.fetch_and_save_metadata(
        entity_type="movie",
        entity_id=movie_id,
        external_id="tt9999999",
    ) is False


def test_service_requires_provider_for_fetch() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    service = MetadataService(repository)

    movie_id = repository.create_movie(title="Inception", year=2010)

    with pytest.raises(ValueError, match="metadata provider"):
        service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=movie_id,
            external_id="tt1375666",
        )


def test_service_accepts_provider_per_call() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)
    service = MetadataService(repository)

    provider = StaticMetadataProvider(
        {
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "overview": "A chemistry teacher enters the drug trade.",
                "genres": ["Drama"],
                "external_id": "tt0903747",
                "metadata_version": "v2",
            }
        }
    )

    tv_id = repository.create_tv_show(title="Breaking Bad", year=2008)

    assert service.fetch_and_save_metadata(
        entity_type="tv",
        entity_id=tv_id,
        external_id="tt0903747",
        provider=provider,
    ) is True

    source = repository.get_metadata_source(
        "tv",
        tv_id,
        "static",
    )

    assert source is not None
    assert source["metadata_version"] == "v2"


def test_provider_metadata_is_passed_without_loss() -> None:
    connection = _connection()
    repository = MetadataRepository(connection)

    class RecordingProvider(StaticMetadataProvider):
        name = "recording"

    provider = RecordingProvider(
        {
            "movie:tt123": {
                "title": "Dune",
                "year": "2021",
                "overview": "Desert epic.",
                "genres": ["Sci-Fi", "Drama"],
                "external_id": "tt123",
                "metadata_version": "2021.1",
            }
        }
    )

    service = MetadataService(repository, provider)
    movie_id = repository.create_movie(title="Dune", year=2021)

    assert service.fetch_and_save_metadata(
        entity_type="movie",
        entity_id=movie_id,
        external_id="tt123",
    ) is True

    source = repository.get_metadata_source(
        "movie",
        movie_id,
        "recording",
    )

    assert source is not None
    assert source["metadata_version"] == "2021.1"
