from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock

import pytest

from app.database.schema import initialize
from app.metadata.omdb_provider import OMDbMetadataProvider
from app.metadata.provider import ProviderMetadata
from app.metadata.registry import MetadataProviderRegistry
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


class TestOmdbRegistryIntegration:
    def test_omdb_registered_and_resolved(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Title": "Inception",
            "Year": "2010",
            "Genre": "Action,Sci-Fi",
            "Plot": "Dreams.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        registry = MetadataProviderRegistry()
        registry.register(provider)

        assert registry.has("omdb") is True
        assert registry.get("omdb") is provider

    def test_service_resolves_provider_by_name(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Title": "Inception",
            "Year": "2010",
            "Genre": "Action",
            "Plot": "Dreams.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)

        movie_id = repo.create_movie(title="Inception")

        result = service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=movie_id,
            external_id="tt1375666",
            provider_name="omdb",
        )

        assert result is True
        genres = repo.get_movie_genres(movie_id)
        assert "Action" in genres

    def test_registry_unknown_provider_falls_back(self) -> None:
        from app.metadata.provider import StaticMetadataProvider

        static = StaticMetadataProvider({
            "movie:tt123": {
                "title": "Static Movie",
                "year": 2024,
                "genres": ["Drama"],
                "external_id": "tt123",
            }
        })

        registry = MetadataProviderRegistry()
        registry.register(static)

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=static, registry=registry)

        movie_id = repo.create_movie(title="Test")

        result = service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=movie_id,
            external_id="tt123",
            provider_name="nonexistent",
        )

        assert result is True
        genres = repo.get_movie_genres(movie_id)
        assert "Drama" in genres

    def test_direct_provider_takes_precedence(self) -> None:
        from app.metadata.provider import StaticMetadataProvider

        direct = StaticMetadataProvider({
            "movie:tt123": {
                "title": "Direct Provider",
                "year": 2024,
                "genres": ["Comedy"],
                "external_id": "tt123",
            }
        })

        registry_provider = StaticMetadataProvider({
            "movie:tt123": {
                "title": "Registry Provider",
                "year": 2024,
                "genres": ["Horror"],
                "external_id": "tt123",
            }
        })

        registry = MetadataProviderRegistry()
        registry.register(registry_provider)

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=direct, registry=registry)

        movie_id = repo.create_movie(title="Test")

        # When provider is passed directly, it takes precedence
        result = service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=movie_id,
            external_id="tt123",
            provider=direct,
        )

        assert result is True
        genres = repo.get_movie_genres(movie_id)
        assert "Comedy" in genres

    def test_registry_used_when_no_direct_provider(self) -> None:
        from app.metadata.provider import StaticMetadataProvider

        registry_provider = StaticMetadataProvider({
            "movie:tt123": {
                "title": "Registry Provider",
                "year": 2024,
                "genres": ["Horror"],
                "external_id": "tt123",
            }
        })

        registry = MetadataProviderRegistry()
        registry.register(registry_provider)

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)

        movie_id = repo.create_movie(title="Test")

        result = service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=movie_id,
            external_id="tt123",
            provider_name="static",
        )

        assert result is True
        genres = repo.get_movie_genres(movie_id)
        assert "Horror" in genres

    def test_tv_through_omdb_registry(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Title": "Breaking Bad",
            "Year": "2008–2013",
            "Genre": "Drama,Crime,Thriller",
            "Plot": "Chemistry teacher.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="test_key", session=mock_session)
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)

        tv_id = repo.create_tv_show(title="Breaking Bad")

        result = service.fetch_and_save_metadata(
            entity_type="tv",
            entity_id=tv_id,
            external_id="tt0903747",
            provider_name="omdb",
        )

        assert result is True
        genres = repo.get_tv_genres(tv_id)
        assert "Drama" in genres
        assert "Crime" in genres
        assert "Thriller" in genres
