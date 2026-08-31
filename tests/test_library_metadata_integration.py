from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.database.schema import initialize
from app.domain.media import MediaType
from app.metadata.identifier import IdentificationResult
from app.metadata.library_integration import LibraryMetadataIntegration
from app.metadata.omdb_provider import OMDbMetadataProvider
from app.metadata.provider import MetadataProvider, ProviderMetadata, StaticMetadataProvider
from app.metadata.registry import MetadataProviderRegistry
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


class TestLibraryMetadataIntegrationMovie:
    def test_movie_with_imdb_id(self) -> None:
        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "Dreams.",
                "genres": ["Sci-Fi", "Action"],
                "external_id": "tt1375666",
            }
        })
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Inception",
            year=2010,
            provider="static",
            external_id="tt1375666",
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        assert lib_result.resolution.entity_type == "movie"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is True

        genres = repo.get_movie_genres(lib_result.resolution.entity_id)
        assert "Sci-Fi" in genres
        assert "Action" in genres

    def test_movie_without_external_id(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Local Movie",
            year=2024,
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        assert lib_result.resolution.entity_type == "movie"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is False

    def test_movie_duplicate_external_id(self) -> None:
        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "genres": ["Sci-Fi"],
                "external_id": "tt1375666",
            }
        })
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        result1 = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Inception",
            year=2010,
            provider="static",
            external_id="tt1375666",
            confidence=0.8,
        )
        res1 = integration.process_identification(result1)

        result2 = IdentificationResult(
            media_type="movie",
            title="Inception Again",
            year=2010,
            provider="static",
            external_id="tt1375666",
            confidence=0.8,
        )
        res2 = integration.process_identification(result2)

        assert res1.resolution.entity_id == res2.resolution.entity_id
        assert res2.resolution.created is False


class TestLibraryMetadataIntegrationTV:
    def test_tv_with_imdb_id(self) -> None:
        provider = StaticMetadataProvider({
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "overview": "Chemistry teacher.",
                "genres": ["Drama", "Crime"],
                "external_id": "tt0903747",
            }
        })
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.TV_SHOW,
            title="Breaking Bad",
            year=2008,
            provider="static",
            external_id="tt0903747",
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        assert lib_result.resolution.entity_type == "tv"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is True

        genres = repo.get_tv_genres(lib_result.resolution.entity_id)
        assert "Drama" in genres
        assert "Crime" in genres

    def test_episode_maps_to_tv(self) -> None:
        provider = StaticMetadataProvider({
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "genres": ["Drama"],
                "external_id": "tt0903747",
            }
        })
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.EPISODE,
            title="Breaking Bad",
            season=1,
            episode=1,
            provider="static",
            external_id="tt0903747",
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        assert lib_result.resolution.entity_type == "tv"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is True


class TestLibraryMetadataIntegrationProviderFailure:
    def test_provider_failure_does_not_corrupt(self) -> None:
        class FailingProvider(MetadataProvider):
            name = "failing"

            def fetch_metadata(self, *, entity_type: str, external_id: str):
                raise ConnectionError("network error")

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=FailingProvider())
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Test Movie",
            year=2024,
            provider="failing",
            external_id="tt999",
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is False

        entity_id = lib_result.resolution.entity_id
        eids = repo.list_external_ids("movie", entity_id)
        assert len(eids) == 1
        assert eids[0]["external_id"] == "tt999"

    def test_provider_not_found_returns_none(self) -> None:
        provider = StaticMetadataProvider({})
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Test Movie",
            year=2024,
            provider="static",
            external_id="tt999",
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is False


class TestLibraryMetadataIntegrationIdempotent:
    def test_second_processing_reuses_entity(self) -> None:
        provider = StaticMetadataProvider({
            "movie:tt123": {
                "title": "Test Movie",
                "year": 2024,
                "genres": ["Action"],
                "external_id": "tt123",
            }
        })
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Test Movie",
            year=2024,
            provider="static",
            external_id="tt123",
            confidence=0.8,
        )

        res1 = integration.process_identification(result)
        res2 = integration.process_identification(result)

        assert res1.resolution.entity_id == res2.resolution.entity_id
        assert res2.resolution.created is False

        eids = repo.list_external_ids("movie", res1.resolution.entity_id)
        assert len(eids) == 1


class TestLibraryMetadataIntegrationRegistry:
    def test_registry_based_provider_selection(self) -> None:
        mock_provider = StaticMetadataProvider({
            "movie:tt456": {
                "title": "Registry Movie",
                "year": 2024,
                "genres": ["Thriller"],
                "external_id": "tt456",
            }
        })

        registry = MetadataProviderRegistry()
        registry.register(mock_provider)

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Registry Movie",
            year=2024,
            provider="static",
            external_id="tt456",
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        assert lib_result.metadata_fetched is True

        genres = repo.get_movie_genres(lib_result.resolution.entity_id)
        assert "Thriller" in genres
