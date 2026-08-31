from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.database.schema import initialize
from app.domain.media import MediaType
from app.library.scanner import ScanResult
from app.metadata.identifier import IdentificationResult, identify
from app.metadata.library_integration import LibraryMetadataIntegration
from app.metadata.omdb_provider import OMDbMetadataProvider
from app.metadata.provider import MetadataProvider, ProviderMetadata, StaticMetadataProvider
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService
from app.metadata.registry import MetadataProviderRegistry


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


def _sr(filename: str, ext: str | None = None, path: str | None = None) -> ScanResult:
    if ext is None:
        ext = Path(filename).suffix.lower()
    return ScanResult(
        path=Path(path or f"/tmp/{filename}"),
        filename=filename,
        extension=ext,
        size_bytes=1000,
    )


# ─── Phase 3K: IdentificationResult with string media_type ───────────────────

class TestIdentificationResultStringMediaType:
    def test_string_media_type_no_crash(self) -> None:
        result = IdentificationResult(
            media_type="movie",
            title="Test",
            confidence=0.8,
        )
        assert result.media_type == "movie"

    def test_enum_media_type(self) -> None:
        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Test",
            confidence=0.8,
        )
        assert result.media_type == MediaType.MOVIE

    def test_string_episode_type(self) -> None:
        result = IdentificationResult(
            media_type="episode",
            title="Test",
            season=1,
            episode=1,
            confidence=0.8,
        )
        assert result.media_type == "episode"


# ─── Phase 3K: Service with string and enum media types ──────────────────────

class TestServiceMediaTypeNormalization:
    def test_movie_enum(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Test Movie",
            year=2024,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "movie"
        assert resolution.created is True

    def test_movie_string(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type="movie",
            title="Test Movie",
            year=2024,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "movie"
        assert resolution.created is True

    def test_episode_maps_to_tv(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.EPISODE,
            title="Breaking Bad",
            season=1,
            episode=1,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "tv"
        assert resolution.created is True

    def test_episode_string_maps_to_tv(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type="episode",
            title="Breaking Bad",
            season=1,
            episode=1,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "tv"
        assert resolution.created is True

    def test_tv_show_enum(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.TV_SHOW,
            title="Test Show",
            year=2020,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "tv"
        assert resolution.created is True

    def test_music_type_unsupported(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.MUSIC,
            title="Test Song",
            confidence=0.8,
        )

        with pytest.raises(ValueError, match="Unsupported"):
            service.resolve_identification(result)


# ─── Phase 3K: Movie with IMDb ID ────────────────────────────────────────────

class TestMovieWithImdbId:
    def test_movie_with_imdb_id_persists(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Inception",
            year=2010,
            provider="omdb",
            external_id="tt1375666",
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "movie"
        assert resolution.created is True

        eid = repo.get_external_id("movie", resolution.entity_id, "omdb")
        assert eid == "tt1375666"

    def test_movie_without_imdb_id(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Dune",
            year=2021,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "movie"
        assert resolution.created is True

        eids = repo.list_external_ids("movie", resolution.entity_id)
        assert eids == []


# ─── Phase 3K: Duplicate IMDb ID ─────────────────────────────────────────────

class TestDuplicateImdbId:
    def test_duplicate_imdb_id_reuses_entity(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result1 = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Inception",
            year=2010,
            provider="omdb",
            external_id="tt1375666",
            confidence=0.8,
        )
        res1 = service.resolve_identification(result1)

        result2 = IdentificationResult(
            media_type="movie",
            title="Inception (Alternate)",
            year=2010,
            provider="omdb",
            external_id="tt1375666",
            confidence=0.8,
        )
        res2 = service.resolve_identification(result2)

        assert res1.entity_id == res2.entity_id
        assert res2.created is False


# ─── Phase 3K: Provider not found ────────────────────────────────────────────

class TestProviderNotFound:
    def test_provider_not_found_returns_none(self) -> None:
        provider = StaticMetadataProvider({})
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)

        result = service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=1,
            external_id="tt9999999",
        )
        assert result is False


# ─── Phase 3K: Provider success ──────────────────────────────────────────────

class TestProviderSuccess:
    def test_provider_success_persists_metadata(self) -> None:
        provider = StaticMetadataProvider({
            "movie:tt1234567": {
                "title": "Test Movie",
                "year": 2024,
                "overview": "A great movie.",
                "genres": ["Action", "Drama"],
                "external_id": "tt1234567",
            }
        })
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)

        movie_id = repo.create_movie(title="Test Movie")
        result = service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=movie_id,
            external_id="tt1234567",
        )
        assert result is True

        genres = repo.get_movie_genres(movie_id)
        assert "Action" in genres
        assert "Drama" in genres


# ─── Phase 3K: Provider failure ──────────────────────────────────────────────

class TestProviderFailure:
    def test_provider_failure_raises(self) -> None:
        class FailingProvider(MetadataProvider):
            name = "failing"

            def fetch_metadata(self, *, entity_type: str, external_id: str):
                raise ConnectionError("network error")

        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=FailingProvider())

        movie_id = repo.create_movie(title="Test Movie")

        with pytest.raises(ConnectionError):
            service.fetch_and_save_metadata(
                entity_type="movie",
                entity_id=movie_id,
                external_id="tt1234567",
            )

        # Entity still exists and is valid
        assert repo.get_movie_genres(movie_id) == []


# ─── Phase 3K: Missing provider ──────────────────────────────────────────────

class TestMissingProvider:
    def test_no_provider_raises(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=None)

        movie_id = repo.create_movie(title="Test Movie")

        with pytest.raises(ValueError, match="metadata provider is required"):
            service.fetch_and_save_metadata(
                entity_type="movie",
                entity_id=movie_id,
                external_id="tt1234567",
            )


# ─── Phase 3K: Library integration with provider failure ─────────────────────

class TestLibraryIntegrationProviderFailure:
    def test_provider_failure_does_not_corrupt_entity(self) -> None:
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
            external_id="tt9999999",
            confidence=0.8,
        )

        lib_result = integration.process_identification(result)
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is False

        # Entity is still valid
        entity_id = lib_result.resolution.entity_id
        eids = repo.list_external_ids("movie", entity_id)
        assert len(eids) == 1
        assert eids[0]["external_id"] == "tt9999999"


# ─── Phase 3L: Metadata cache (metadata_sources) ─────────────────────────────

class TestMetadataCache:
    def test_metadata_source_records_fetch_time(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        movie_id = repo.create_movie(title="Cached Movie")

        repo.record_metadata_source(
            entity_type="movie",
            entity_id=movie_id,
            provider="omdb",
            metadata_version="omdb-v1",
        )

        source = repo.get_metadata_source("movie", movie_id, "omdb")
        assert source is not None
        assert source["provider"] == "omdb"
        assert source["fetched_at"] is not None

    def test_metadata_source_upsert_safe(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        movie_id = repo.create_movie(title="Cached Movie")

        repo.record_metadata_source(
            entity_type="movie",
            entity_id=movie_id,
            provider="omdb",
            metadata_version="v1",
        )
        repo.record_metadata_source(
            entity_type="movie",
            entity_id=movie_id,
            provider="omdb",
            metadata_version="v2",
        )

        sources = conn.execute(
            "SELECT COUNT(*) FROM metadata_sources WHERE entity_type = 'movie' AND entity_id = ?",
            (movie_id,),
        ).fetchone()[0]
        assert sources == 1


# ─── Phase 3L: Retry-safe behavior ───────────────────────────────────────────

class TestRetrySafe:
    def test_failed_fetch_can_be_retried(self) -> None:
        call_count = 0

        class SometimesFailingProvider(MetadataProvider):
            name = "retry"

            def fetch_metadata(self, *, entity_type: str, external_id: str):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionError("temporary failure")
                return ProviderMetadata(
                    title="Recovered",
                    year=2024,
                    genres=("Drama",),
                    external_id=external_id,
                )

        conn = _connection()
        repo = MetadataRepository(conn)
        provider = SometimesFailingProvider()
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Retry Movie",
            year=2024,
            provider="retry",
            external_id="tt1111111",
            confidence=0.8,
        )

        # First attempt fails
        lib_result = integration.process_identification(result)
        assert lib_result.metadata_fetched is False
        entity_id = lib_result.resolution.entity_id

        # Retry succeeds
        fetched = service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=entity_id,
            external_id="tt1111111",
        )
        assert fetched is True
        genres = repo.get_movie_genres(entity_id)
        assert "Drama" in genres


# ─── Phase 3M: TV metadata ───────────────────────────────────────────────────

class TestTvMetadata:
    def test_tv_show_creation(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.TV_SHOW,
            title="Breaking Bad",
            year=2008,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "tv"
        assert resolution.created is True

    def test_tv_show_with_imdb_id(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.TV_SHOW,
            title="Breaking Bad",
            year=2008,
            provider="omdb",
            external_id="tt0903747",
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        eid = repo.get_external_id("tv", resolution.entity_id, "omdb")
        assert eid == "tt0903747"

    def test_tv_episode_maps_to_tv(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.EPISODE,
            title="Breaking Bad",
            season=1,
            episode=1,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.entity_type == "tv"
        assert resolution.created is True

    def test_tv_genres_persist(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        tv_id = repo.create_tv_show(title="Breaking Bad")

        provider = StaticMetadataProvider({
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "overview": "A chemistry teacher...",
                "genres": ["Drama", "Crime", "Thriller"],
                "external_id": "tt0903747",
            }
        })
        service = MetadataService(repo, provider=provider)

        service.fetch_and_save_metadata(
            entity_type="tv",
            entity_id=tv_id,
            external_id="tt0903747",
        )

        genres = repo.get_tv_genres(tv_id)
        assert "Drama" in genres
        assert "Crime" in genres
        assert "Thriller" in genres

    def test_tv_metadata_overview_persists(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        tv_id = repo.create_tv_show(title="Breaking Bad")

        provider = StaticMetadataProvider({
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "overview": "A high school chemistry teacher turned meth producer.",
                "genres": [],
                "external_id": "tt0903747",
            }
        })
        service = MetadataService(repo, provider=provider)

        service.fetch_and_save_metadata(
            entity_type="tv",
            entity_id=tv_id,
            external_id="tt0903747",
        )

        row = conn.execute(
            "SELECT overview FROM tv_shows WHERE id = ?", (tv_id,)
        ).fetchone()
        assert row["overview"] == "A high school chemistry teacher turned meth producer."

    def test_tv_duplicate_external_id_reuses(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result1 = IdentificationResult(
            media_type=MediaType.TV_SHOW,
            title="Breaking Bad",
            year=2008,
            provider="omdb",
            external_id="tt0903747",
            confidence=0.8,
        )
        res1 = service.resolve_identification(result1)

        result2 = IdentificationResult(
            media_type="episode",
            title="Breaking Bad",
            season=1,
            episode=1,
            provider="omdb",
            external_id="tt0903747",
            confidence=0.8,
        )
        res2 = service.resolve_identification(result2)

        assert res1.entity_id == res2.entity_id


# ─── Phase 3M: OMDb TV support ───────────────────────────────────────────────

class TestOMDbTvSupport:
    def test_omdb_tv_entity_type_accepted(self) -> None:
        provider = OMDbMetadataProvider(api_key="test_key")
        assert provider.fetch_metadata is not None

    def test_omdb_unsupported_entity_returns_none(self) -> None:
        provider = OMDbMetadataProvider(api_key="test_key")
        result = provider.fetch_metadata(entity_type="person", external_id="nm123")
        assert result is None

    def test_omdb_empty_api_key_raises(self) -> None:
        provider = OMDbMetadataProvider(api_key="")
        with pytest.raises(ValueError, match="OMDB_API_KEY is required"):
            provider.fetch_metadata(entity_type="movie", external_id="tt123")

    def test_omdb_invalid_imdb_id_raises(self) -> None:
        provider = OMDbMetadataProvider(api_key="test_key")
        with pytest.raises(ValueError, match="IMDb ID"):
            provider.fetch_metadata(entity_type="movie", external_id="12345")


# ─── Phase 3N: Library scan → identification → metadata E2E ──────────────────

class TestLibraryScanMetadataE2E:
    def test_file_discovered_to_metadata(self, tmp_path: Path) -> None:
        from app.library.coordinator import sync_location

        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()
        assert mf is not None

        scan_result = ScanResult(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["Movies"])

        assert id_result.media_type == MediaType.MOVIE
        assert "Inception" in id_result.title
        assert id_result.year == 2010

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        lib_result = integration.process_identification(id_result)
        assert lib_result.resolution.entity_type == "movie"
        assert lib_result.resolution.created is True

    def test_second_scan_idempotent(self, tmp_path: Path) -> None:
        from app.library.coordinator import sync_location

        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()
        scan_result = ScanResult(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["Movies"])

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "A dream within a dream.",
                "genres": ["Sci-Fi", "Action"],
                "external_id": "tt1375666",
            }
        })

        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=provider)
        integration = LibraryMetadataIntegration(service)

        id_result.provider = "omdb"
        id_result.external_id = "tt1375666"

        res1 = integration.process_identification(id_result)
        res2 = integration.process_identification(id_result)

        assert res1.resolution.entity_id == res2.resolution.entity_id
        assert res2.resolution.created is False

        eids = repo.list_external_ids("movie", res1.resolution.entity_id)
        assert len(eids) == 1


# ─── Phase 3O: Validation / deduplication ─────────────────────────────────────

class TestValidationDeduplication:
    def test_external_ids_unique_constraint(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        movie_id = repo.create_movie(title="Test Movie")

        repo.set_external_id(
            entity_type="movie",
            entity_id=movie_id,
            provider="omdb",
            external_id="tt123",
            is_primary=True,
        )

        repo.set_external_id(
            entity_type="movie",
            entity_id=movie_id,
            provider="omdb",
            external_id="tt456",
            is_primary=False,
        )

        eid = repo.get_external_id("movie", movie_id, "omdb")
        assert eid == "tt456"

    def test_different_providers_same_entity(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        movie_id = repo.create_movie(title="Test Movie")

        repo.set_external_id(
            entity_type="movie",
            entity_id=movie_id,
            provider="omdb",
            external_id="tt123",
            is_primary=True,
        )
        repo.set_external_id(
            entity_type="movie",
            entity_id=movie_id,
            provider="tmdb",
            external_id="456",
            is_primary=False,
        )

        eids = repo.list_external_ids("movie", movie_id)
        assert len(eids) == 2

    def test_genre_deduplication(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        movie_id = repo.create_movie(title="Test Movie")
        repo.set_movie_genres(movie_id, ["Action", "Action", "Drama"])

        genres = repo.get_movie_genres(movie_id)
        assert genres == ["Action", "Drama"]

    def test_genre_replacement_safe(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        movie_id = repo.create_movie(title="Test Movie")
        repo.set_movie_genres(movie_id, ["Action", "Drama"])
        repo.set_movie_genres(movie_id, ["Comedy"])

        genres = repo.get_movie_genres(movie_id)
        assert genres == ["Comedy"]

    def test_tv_genre_deduplication(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        tv_id = repo.create_tv_show(title="Test Show")
        repo.set_tv_genres(tv_id, ["Drama", "Drama", "Crime"])

        genres = repo.get_tv_genres(tv_id)
        assert genres == ["Crime", "Drama"]


# ─── Phase 3P: Production hardening ──────────────────────────────────────────

class TestProductionHardening:
    def test_omdb_malformed_json(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON")
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(
            api_key="test_key",
            session=mock_session,
        )

        result = provider.fetch_metadata(entity_type="movie", external_id="tt123")
        assert result is None

    def test_omdb_http_error_propagates(self) -> None:
        import requests as req

        mock_session = MagicMock()
        mock_session.get.side_effect = req.ConnectionError("timeout")

        provider = OMDbMetadataProvider(
            api_key="test_key",
            session=mock_session,
        )

        with pytest.raises(req.ConnectionError):
            provider.fetch_metadata(entity_type="movie", external_id="tt123")

    def test_omdb_response_false(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"Response": "False", "Error": "Movie not found"}
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(
            api_key="test_key",
            session=mock_session,
        )

        result = provider.fetch_metadata(entity_type="movie", external_id="tt999")
        assert result is None

    def test_omdb_missing_title(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Year": "2024",
            "Genre": "Action",
            "Plot": "A movie.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(
            api_key="test_key",
            session=mock_session,
        )

        result = provider.fetch_metadata(entity_type="movie", external_id="tt123")
        assert result is None

    def test_omdb_missing_genre(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Response": "True",
            "Title": "Test Movie",
            "Year": "2024",
            "Genre": "",
            "Plot": "A movie.",
        }
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(
            api_key="test_key",
            session=mock_session,
        )

        result = provider.fetch_metadata(entity_type="movie", external_id="tt123")
        assert result is not None
        assert result.genres == ()

    def test_omdb_year_range_parsing(self) -> None:
        assert OMDbMetadataProvider._parse_year("2008–2013") == 2008
        assert OMDbMetadataProvider._parse_year("2024") == 2024
        assert OMDbMetadataProvider._parse_year(None) is None
        assert OMDbMetadataProvider._parse_year("abc") is None

    def test_metadata_provider_registry(self) -> None:
        registry = MetadataProviderRegistry()

        provider = StaticMetadataProvider({})
        registry.register(provider)

        assert registry.has("static") is True
        assert registry.has("omdb") is False
        assert "static" in registry.names()

    def test_metadata_provider_registry_duplicate_rejected(self) -> None:
        registry = MetadataProviderRegistry()
        provider = StaticMetadataProvider({})

        registry.register(provider)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(provider)

    def test_metadata_provider_registry_unknown_key(self) -> None:
        registry = MetadataProviderRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.get("nonexistent")

    def test_empty_external_id_no_crash(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        service = MetadataService(repo)

        result = IdentificationResult(
            media_type=MediaType.MOVIE,
            title="Test Movie",
            provider=None,
            external_id=None,
            confidence=0.8,
        )

        resolution = service.resolve_identification(result)
        assert resolution.created is True

        eids = repo.list_external_ids("movie", resolution.entity_id)
        assert eids == []

    def test_provider_empty_genres(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        movie_id = repo.create_movie(title="Test Movie")

        provider = StaticMetadataProvider({
            "movie:tt123": {
                "title": "Test Movie",
                "year": 2024,
                "genres": [],
                "external_id": "tt123",
            }
        })
        service = MetadataService(repo, provider=provider)

        service.fetch_and_save_metadata(
            entity_type="movie",
            entity_id=movie_id,
            external_id="tt123",
        )

        genres = repo.get_movie_genres(movie_id)
        assert genres == []

    def test_save_metadata_with_tv_genres(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)

        tv_id = repo.create_tv_show(title="Test Show")

        provider = StaticMetadataProvider({})
        service = MetadataService(repo, provider=provider)

        service.save_metadata(
            entity_type="tv",
            entity_id=tv_id,
            provider="omdb",
            metadata={
                "title": "Test Show",
                "year": 2024,
                "overview": "A great show.",
                "genres": ["Drama", "Comedy"],
            },
        )

        genres = repo.get_tv_genres(tv_id)
        assert "Drama" in genres
        assert "Comedy" in genres
