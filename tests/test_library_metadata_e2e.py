from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.database.schema import initialize
from app.domain.media import MediaType
from app.library.scanner import ScanResult
from app.metadata.identifier import IdentificationResult, identify
from app.metadata.library_integration import LibraryMetadataIntegration
from app.metadata.provider import StaticMetadataProvider
from app.metadata.registry import MetadataProviderRegistry
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


class TestLibraryToMetadataE2E:
    def test_movie_with_imdb_e2e(self) -> None:
        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "Dreams within dreams.",
                "genres": ["Sci-Fi", "Action", "Thriller"],
                "external_id": "tt1375666",
            }
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        scan_result = ScanResult(
            path=Path("/tmp/Inception (2010).mkv"),
            filename="Inception (2010).mkv",
            extension=".mkv",
            size_bytes=1000,
        )
        id_result = identify(scan_result, parent_parts=["Movies"])

        assert id_result.media_type == MediaType.MOVIE
        assert "Inception" in id_result.title
        assert id_result.year == 2010

        id_result.provider = "static"
        id_result.external_id = "tt1375666"

        lib_result = integration.process_identification(id_result)

        assert lib_result.resolution.entity_type == "movie"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is True

        entity_id = lib_result.resolution.entity_id
        genres = repo.get_movie_genres(entity_id)
        assert "Sci-Fi" in genres
        assert "Action" in genres
        assert "Thriller" in genres

        eids = repo.list_external_ids("movie", entity_id)
        assert len(eids) == 1
        assert eids[0]["external_id"] == "tt1375666"

        source = repo.get_metadata_source("movie", entity_id, "static")
        assert source is not None

    def test_tv_with_imdb_e2e(self) -> None:
        provider = StaticMetadataProvider({
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "overview": "A chemistry teacher.",
                "genres": ["Drama", "Crime", "Thriller"],
                "external_id": "tt0903747",
            }
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        scan_result = ScanResult(
            path=Path("/tmp/Breaking.Bad.S01E01.720p.mkv"),
            filename="Breaking.Bad.S01E01.720p.mkv",
            extension=".mkv",
            size_bytes=1000,
        )
        id_result = identify(scan_result, parent_parts=["TV Shows", "Breaking Bad"])

        assert id_result.media_type == MediaType.EPISODE
        assert "Breaking Bad" in id_result.title
        assert id_result.season == 1
        assert id_result.episode == 1

        id_result.provider = "static"
        id_result.external_id = "tt0903747"

        lib_result = integration.process_identification(id_result)

        assert lib_result.resolution.entity_type == "tv"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is True

        entity_id = lib_result.resolution.entity_id
        genres = repo.get_tv_genres(entity_id)
        assert "Drama" in genres
        assert "Crime" in genres

    def test_local_movie_without_external_id(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        scan_result = ScanResult(
            path=Path("/tmp/My.Movie.2024.mkv"),
            filename="My.Movie.2024.mkv",
            extension=".mkv",
            size_bytes=1000,
        )
        id_result = identify(scan_result, parent_parts=["Movies"])

        assert id_result.media_type == MediaType.MOVIE
        assert id_result.year == 2024

        lib_result = integration.process_identification(id_result)

        assert lib_result.resolution.entity_type == "movie"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is False

        entity_id = lib_result.resolution.entity_id
        eids = repo.list_external_ids("movie", entity_id)
        assert eids == []

    def test_duplicate_external_id_idempotent(self) -> None:
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

        result1 = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Test Movie",
            year=2024,
            provider="static",
            external_id="tt123",
            confidence=0.8,
        )
        res1 = integration.process_identification(result1)

        result2 = IdentificationResult(
            media_type="movie",
            title="Test Movie Again",
            year=2024,
            provider="static",
            external_id="tt123",
            confidence=0.8,
        )
        res2 = integration.process_identification(result2)

        assert res1.resolution.entity_id == res2.resolution.entity_id
        assert res2.resolution.created is False

        eids = repo.list_external_ids("movie", res1.resolution.entity_id)
        assert len(eids) == 1

    def test_provider_failure_e2e(self) -> None:
        class FailingProvider(StaticMetadataProvider):
            name = "failing"

            def fetch_metadata(self, **kwargs):
                raise ConnectionError("network down")

        provider = FailingProvider({})
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
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

    def test_genre_persistence_e2e(self) -> None:
        provider = StaticMetadataProvider({
            "movie:tt789": {
                "title": "Genre Movie",
                "year": 2024,
                "genres": ["Action", "Comedy", "Drama"],
                "external_id": "tt789",
            }
        })

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Genre Movie",
            year=2024,
            provider="static",
            external_id="tt789",
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        entity_id = lib_result.resolution.entity_id

        genres = repo.get_movie_genres(entity_id)
        assert sorted(genres) == ["Action", "Comedy", "Drama"]

        source = repo.get_metadata_source("movie", entity_id, "static")
        assert source is not None
        assert source["fetched_at"] is not None
