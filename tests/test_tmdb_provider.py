"""Tests for the TMDB metadata provider, discovery, and artwork pipeline."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.config import TmdbConfig
from app.database.schema import initialize
from app.domain.media import MediaType
from app.library.coordinator import process_library_metadata, sync_location
from app.library.library_repository import LibraryRepository
from app.library.scanner import ScanResult
from app.metadata.artwork_downloader import download_artwork
from app.metadata.identifier import IdentificationResult, identify
from app.metadata.library_integration import LibraryMetadataIntegration
from app.metadata.omdb_provider import OMDbMetadataProvider
from app.metadata.provider import MetadataProvider, ProviderMetadata, StaticMetadataProvider
from app.metadata.registry import MetadataProviderRegistry
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService
from app.metadata.tmdb_provider import TmdbMetadataProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize(conn)
    return conn


def _mock_tmdb_provider(
    search_hits: list[dict] | None = None,
    details: dict | None = None,
    external_ids: dict | None = None,
    credits: dict | None = None,
) -> TmdbMetadataProvider:
    """Create a TMDB provider with mocked HTTP responses."""
    session = MagicMock()
    resp = MagicMock()

    def _json_side_effect():
        # Route based on URL path
        url = session.get.call_args[0][0] if session.get.call_args else ""
        if "search/movie" in url or "search/tv" in url:
            return {"results": search_hits or []}
        if "external_ids" in url:
            return external_ids or {}
        if "credits" in url:
            return credits or {"cast": [], "crew": []}
        return details or {}

    resp.json.side_effect = _json_side_effect
    resp.raise_for_status.return_value = None
    session.get.return_value = resp
    return TmdbMetadataProvider(api_key="test_key", session=session)


def _make_sync(tmp: Path, filenames: list[str]) -> tuple[sqlite3.Connection, Path]:
    """Create a temp DB + library dir with dummy files, run sync."""
    conn = _connection()
    repo = LibraryRepository(conn)
    repo.add_location(tmp, label=str(tmp))
    conn.commit()
    sync_location(conn, tmp)
    return conn, tmp


# ---------------------------------------------------------------------------
# TMDB Provider unit tests
# ---------------------------------------------------------------------------


class TestTmdbProviderConfig:
    def test_reads_api_key_from_env(self) -> None:
        with patch.dict("os.environ", {"TMDB_API_KEY": "my_test_key"}):
            provider = TmdbMetadataProvider()
            assert provider.api_key == "my_test_key"

    def test_reads_api_key_from_config(self) -> None:
        config = TmdbConfig(api_key="config_key")
        provider = TmdbMetadataProvider(config=config)
        assert provider.api_key == "config_key"

    def test_empty_api_key_raises_on_search(self) -> None:
        provider = TmdbMetadataProvider(api_key="")
        with pytest.raises(ValueError, match="TMDB_API_KEY"):
            provider.search(entity_type="movie", query="Test")

    def test_empty_api_key_raises_on_fetch(self) -> None:
        provider = TmdbMetadataProvider(api_key="")
        with pytest.raises(ValueError, match="TMDB_API_KEY"):
            provider.fetch_metadata(entity_type="movie", external_id="123")


class TestTmdbSearch:
    def test_search_returns_hits(self) -> None:
        provider = _mock_tmdb_provider(search_hits=[
            {"id": 12345, "title": "Example Show", "media_type": "tv",
             "vote_average": 8.5, "poster_path": "/abc.jpg"},
        ])
        results = provider.search(entity_type="tv", query="Example Show")
        assert len(results) == 1
        assert results[0]["id"] == 12345
        assert results[0]["title"] == "Example Show"

    def test_search_returns_empty_for_no_match(self) -> None:
        provider = _mock_tmdb_provider(search_hits=[])
        results = provider.search(entity_type="tv", query="Nonexistent")
        assert results == []

    def test_search_ignores_invalid_entity_type(self) -> None:
        provider = _mock_tmdb_provider()
        results = provider.search(entity_type="music", query="test")
        assert results == []

    def test_search_promotes_year_match(self) -> None:
        provider = _mock_tmdb_provider(search_hits=[
            {"id": 1, "title": "Show A", "media_type": "tv",
             "vote_average": 9.0, "year": 2020,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2020-01-01"},
            {"id": 2, "title": "Show B", "media_type": "tv",
             "vote_average": 9.5, "year": 2019,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2019-01-01"},
        ])
        results = provider.search(entity_type="tv", query="Show", year=2020)
        assert results[0]["id"] == 1  # year match first
        assert results[1]["id"] == 2

    def test_search_handles_http_error(self) -> None:
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.ConnectionError("fail")
        provider = TmdbMetadataProvider(api_key="key", session=mock_session)
        results = provider.search(entity_type="tv", query="test")
        assert results == []

    def test_search_handles_malformed_json(self) -> None:
        provider = _mock_tmdb_provider()
        provider.session.get.return_value.json.side_effect = ValueError("bad")
        results = provider.search(entity_type="tv", query="test")
        assert results == []


class TestTmdbFetchMetadata:
    def test_fetch_returns_normalized_metadata(self) -> None:
        details = {
            "id": 12345,
            "title": "Test Movie",
            "release_date": "2024-01-15",
            "overview": "A great movie.",
            "genres": [{"name": "Action"}, {"name": "Drama"}],
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
        }
        external_ids = {"imdb_id": "tt1234567"}
        credits = {"cast": [], "crew": []}
        provider = _mock_tmdb_provider(
            details=details, external_ids=external_ids, credits=credits
        )
        metadata = provider.fetch_metadata(entity_type="movie", external_id="12345")
        assert metadata is not None
        assert metadata.title == "Test Movie"
        assert metadata.year == 2024
        assert metadata.overview == "A great movie."
        assert metadata.genres == ("Action", "Drama")
        assert metadata.tmdb_id == 12345
        assert metadata.imdb_id == "tt1234567"
        assert metadata.poster_path == "/poster.jpg"
        assert metadata.backdrop_path == "/backdrop.jpg"
        assert metadata.external_id == "12345"

    def test_fetch_tv_with_credits(self) -> None:
        details = {
            "id": 67890,
            "name": "Test Show",
            "first_air_date": "2020-03-01",
            "overview": "TV overview",
            "genres": [{"name": "Sci-Fi"}],
            "poster_path": "/p.jpg",
            "backdrop_path": "/b.jpg",
            "number_of_seasons": 2,
            "number_of_episodes": 20,
        }
        credits = {
            "cast": [
                {"name": "Alice", "character": "Hero", "order": "1"},
                {"name": "Bob", "character": "Villain", "order": "2"},
            ],
            "crew": [],
        }
        provider = _mock_tmdb_provider(
            details=details, external_ids={"imdb_id": "tt999"}, credits=credits
        )
        metadata = provider.fetch_metadata(entity_type="tv", external_id="67890")
        assert metadata is not None
        assert metadata.title == "Test Show"
        assert metadata.first_air_date == "2020-03-01"
        assert metadata.number_of_seasons == 2
        assert metadata.number_of_episodes == 20
        assert len(metadata.credits) == 2
        assert metadata.credits[0]["name"] == "Alice"
        assert metadata.credits[0]["character"] == "Hero"

    def test_fetch_handles_http_error(self) -> None:
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.ConnectionError("fail")
        provider = TmdbMetadataProvider(api_key="key", session=mock_session)
        with pytest.raises(requests.ConnectionError):
            provider.fetch_metadata(entity_type="movie", external_id="1")

    def test_fetch_handles_malformed_json(self) -> None:
        provider = _mock_tmdb_provider()
        provider.session.get.return_value.json.side_effect = ValueError("bad")
        result = provider.fetch_metadata(entity_type="movie", external_id="1")
        assert result is None

    def test_fetch_unsupported_type_returns_none(self) -> None:
        provider = TmdbMetadataProvider(api_key="key")
        result = provider.fetch_metadata(entity_type="music", external_id="1")
        assert result is None

    def test_poster_url(self) -> None:
        provider = TmdbMetadataProvider(api_key="key")
        assert provider.poster_url("/abc.jpg") == "https://image.tmdb.org/t/p/w500/abc.jpg"
        assert provider.poster_url(None) is None

    def test_backdrop_url(self) -> None:
        provider = TmdbMetadataProvider(api_key="key")
        assert provider.backdrop_url("/xyz.jpg") == "https://image.tmdb.org/t/p/w1280/xyz.jpg"
        assert provider.backdrop_url(None) is None


class TestTmdbNormalizeMetadata:
    def test_normalizes_from_tmdb_format(self) -> None:
        provider = TmdbMetadataProvider(api_key="key")
        metadata = provider.normalize_metadata({
            "name": "Test",
            "release_date": "2024-05-01",
            "overview": "Plot",
            "genres": [{"name": "Action"}],
            "id": 42,
            "poster_path": "/p.jpg",
            "backdrop_path": "/b.jpg",
            "credits": {"cast": [{"name": "Actor", "character": "Role", "order": "1"}]},
        })
        assert metadata.title == "Test"
        assert metadata.year == 2024
        assert metadata.tmdb_id == 42
        assert metadata.poster_path == "/p.jpg"
        assert len(metadata.credits) == 1

    def test_normalizes_tv_show(self) -> None:
        provider = TmdbMetadataProvider(api_key="key")
        metadata = provider.normalize_metadata({
            "name": "Show",
            "first_air_date": "2020-01-01",
            "number_of_seasons": 3,
            "number_of_episodes": 30,
        })
        assert metadata.title == "Show"
        assert metadata.year == 2020
        assert metadata.first_air_date == "2020-01-01"
        assert metadata.number_of_seasons == 3
        assert metadata.number_of_episodes == 30

    def test_empty_title_raises(self) -> None:
        provider = TmdbMetadataProvider(api_key="key")
        with pytest.raises(ValueError, match="title"):
            provider.normalize_metadata({"title": "", "name": ""})


# ---------------------------------------------------------------------------
# Artwork download tests
# ---------------------------------------------------------------------------


class TestArtworkDownloader:
    def test_download_saves_file(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        mock_resp = MagicMock()
        mock_resp.content = b"fake-image-data"
        mock_resp.raise_for_status.return_value = None
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        result = download_artwork(
            url="https://image.tmdb.org/t/p/w500/poster.jpg",
            local_dir=tmp / "posters",
            entity_id=42,
            artwork_type="poster",
            session=mock_session,
        )
        assert result is not None
        assert Path(result).exists()
        assert Path(result).read_bytes() == b"fake-image-data"

    def test_download_skips_existing_file(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        target = tmp / "posters" / "42.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"existing")

        mock_session = MagicMock()
        result = download_artwork(
            url="https://example.com/new.jpg",
            local_dir=tmp / "posters",
            entity_id=42,
            artwork_type="poster",
            session=mock_session,
        )
        assert result == str(target)
        mock_session.get.assert_not_called()

    def test_download_handles_http_error(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.ConnectionError("fail")
        result = download_artwork(
            url="https://example.com/img.jpg",
            local_dir=tmp / "posters",
            entity_id=99,
            artwork_type="poster",
            session=mock_session,
        )
        assert result is None

    def test_download_handles_no_url(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        result = download_artwork(
            url=None,
            local_dir=tmp / "posters",
            entity_id=1,
            artwork_type="poster",
        )
        assert result is None

    def test_download_handles_empty_content(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        mock_resp = MagicMock()
        mock_resp.content = b""
        mock_resp.raise_for_status.return_value = None
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        result = download_artwork(
            url="https://example.com/img.jpg",
            local_dir=tmp / "posters",
            entity_id=1,
            artwork_type="poster",
            session=mock_session,
        )
        assert result is None


# ---------------------------------------------------------------------------
# End-to-end pipeline with TMDB provider
# ---------------------------------------------------------------------------


class TestTmdbPipeline:
    """Integration tests for the full TMDB pipeline with mocked provider."""

    def test_generic_show_with_tmdb_discovery(self) -> None:
        """Three episodes of a generic show → 1 TV show with correct seasons."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Example.Show.S01E01.1080p.WEB-DL.x264.mkv").write_bytes(b"")
        (tmp / "Example.Show.S01E02.1080p.WEB-DL.x264.mkv").write_bytes(b"")
        (tmp / "Example.Show.S02E01.1080p.WEB-DL.x264.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(
            search_hits=[
                {
                    "id": 99999,
                    "title": "Example Show",
                    "media_type": "tv",
                    "vote_average": 8.0,
                    "poster_path": "/poster.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "first_air_date": "2020-01-01",
                }
            ],
            details={
                "id": 99999,
                "name": "Example Show",
                "first_air_date": "2020-01-01",
                "overview": "A great show.",
                "genres": [{"name": "Drama"}],
                "poster_path": "/poster.jpg",
                "backdrop_path": "/backdrop.jpg",
                "number_of_seasons": 2,
                "number_of_episodes": 3,
            },
            external_ids={"imdb_id": "tt1234567"},
            credits={"cast": [], "crew": []},
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        artwork_dir = Path(tempfile.mkdtemp()) / "artwork"
        # Mock artwork HTTP to avoid real network calls in tests
        mock_art_session = MagicMock()
        mock_art_resp = MagicMock()
        mock_art_resp.content = b"fake-poster-data"
        mock_art_resp.raise_for_status.return_value = None
        mock_art_session.get.return_value = mock_art_resp
        integration = LibraryMetadataIntegration(
            meta_svc, music_service=music_svc, artwork_dir=artwork_dir,
            http_session=mock_art_session,
        )

        # Use the coordinator's process_library_metadata for full pipeline
        process_library_metadata(conn, integration=integration)

        # Verify entity counts
        tv_shows = int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0])
        seasons = int(conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0])
        episodes = int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0])
        episode_files = int(conn.execute("SELECT COUNT(*) FROM episode_files").fetchone()[0])

        assert tv_shows == 1, f"Expected 1 tv_show, got {tv_shows}"
        assert seasons >= 1, f"Expected at least 1 season, got {seasons}"
        assert episodes == 3, f"Expected 3 episodes, got {episodes}"
        assert episode_files == 3, f"Expected 3 episode_files, got {episode_files}"

        # Verify metadata was persisted
        show = conn.execute("SELECT * FROM tv_shows").fetchone()
        assert show["title"] == "Example Show"
        assert show["overview"] == "A great show."
        assert show["tmdb_id"] == 99999

        # Verify external IDs
        eids = meta_repo.list_external_ids("tv", show["id"])
        providers = {e["provider"] for e in eids}
        assert "tmdb" in providers
        assert "imdb" in providers

    def test_idempotent_second_run(self) -> None:
        """Running the pipeline twice produces the same counts."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")
        (tmp / "Show.S01E02.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Show", "media_type": "tv",
                 "vote_average": 7.0, "poster_path": None,
                 "backdrop_path": None, "first_air_date": "2020-01-01"}
            ],
            details={"id": 1, "name": "Show", "first_air_date": "2020-01-01",
                     "overview": "Plot", "genres": [],
                     "poster_path": None, "backdrop_path": None},
            external_ids={"imdb_id": "tt000"},
            credits={"cast": [], "crew": []},
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        artwork_dir = Path(tempfile.mkdtemp()) / "artwork"
        integration = LibraryMetadataIntegration(
            meta_svc, music_service=music_svc, artwork_dir=artwork_dir
        )

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        first = (
            int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episode_files").fetchone()[0]),
        )

        # Second run
        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        second = (
            int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episode_files").fetchone()[0]),
        )

        assert first == second

    def test_no_api_key_falls_back_gracefully(self) -> None:
        """When TMDB key is missing, local identification still works."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        # No TMDB provider registered — only OMDb (which also has no key)
        registry = MetadataProviderRegistry()
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        # Entity should still be created locally
        tv_shows = int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0])
        assert tv_shows == 1

    def test_discovery_selects_best_match(self) -> None:
        """Provider discovery selects the best match for a title."""
        provider = _mock_tmdb_provider(search_hits=[
            {"id": 1, "title": "Other Show", "media_type": "tv",
             "vote_average": 9.0, "year": 2020,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2020-01-01"},
            {"id": 2, "title": "My Show", "media_type": "tv",
             "vote_average": 7.0, "year": 2019,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2019-01-01"},
        ])
        results = provider.search(entity_type="tv", query="My Show", year=2019)
        assert len(results) == 2
        assert results[0]["id"] == 2  # year match promoted
        assert results[0]["title"] == "My Show"


class TestTmdbArtworkPipeline:
    """Verify artwork is downloaded and persisted correctly."""

    def test_artwork_downloaded_and_persisted(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        artwork_cache = Path(tempfile.mkdtemp()) / "artwork"

        mock_resp = MagicMock()
        mock_resp.content = b"poster-data"
        mock_resp.raise_for_status.return_value = None
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Show", "media_type": "tv",
                 "vote_average": 7.0, "poster_path": "/p.jpg",
                 "backdrop_path": "/b.jpg",
                 "first_air_date": "2020-01-01"}
            ],
            details={
                "id": 1, "name": "Show", "first_air_date": "2020-01-01",
                "overview": "Plot", "genres": [],
                "poster_path": "/p.jpg", "backdrop_path": "/b.jpg",
            },
            external_ids={"imdb_id": "tt001"},
            credits={"cast": [], "crew": []},
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(
            meta_svc, music_service=music_svc,
            artwork_dir=artwork_cache, http_session=mock_session,
        )

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        # Verify artwork rows exist
        artwork_rows = meta_repo.list_artwork("tv", 1)
        types = {row["artwork_type"] for row in artwork_rows}
        assert "poster" in types
        assert "backdrop" in types

        # Verify poster file exists on disk
        poster_rows = [r for r in artwork_rows if r["artwork_type"] == "poster"]
        assert len(poster_rows) == 1
        poster_path = poster_rows[0]["local_path"]
        assert poster_path is not None
        assert Path(poster_path).exists()
        assert Path(poster_path).read_bytes() == b"poster-data"

    def test_failed_artwork_download_does_not_create_fake_rows(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        artwork_cache = Path(tempfile.mkdtemp()) / "artwork"

        mock_resp = MagicMock()
        mock_resp.content = b""
        mock_resp.raise_for_status.return_value = None
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Show", "media_type": "tv",
                 "vote_average": 7.0, "poster_path": "/p.jpg",
                 "backdrop_path": None,
                 "first_air_date": "2020-01-01"}
            ],
            details={
                "id": 1, "name": "Show", "first_air_date": "2020-01-01",
                "overview": "Plot", "genres": [],
                "poster_path": "/p.jpg", "backdrop_path": None,
            },
            external_ids={"imdb_id": "tt001"},
            credits={"cast": [], "crew": []},
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(
            meta_svc, music_service=music_svc,
            artwork_dir=artwork_cache, http_session=mock_session,
        )

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        # No artwork row should exist (empty content = no download)
        artwork_rows = meta_repo.list_artwork("tv", 1)
        poster_rows = [r for r in artwork_rows if r["artwork_type"] == "poster"]
        assert len(poster_rows) == 0


class TestTmdbPeoplePipeline:
    """Verify people/cast persistence."""

    def test_credits_persist_people_and_relationships(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Movie.2024.1080p.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Movie", "media_type": "movie",
                 "vote_average": 7.0, "year": 2024,
                 "poster_path": None, "backdrop_path": None}
            ],
            details={
                "id": 1, "title": "Movie", "release_date": "2024-01-01",
                "overview": "Plot", "genres": [],
                "poster_path": None, "backdrop_path": None,
            },
            external_ids={"imdb_id": "tt001"},
            credits={
                "cast": [
                    {"name": "Actor One", "character": "Hero", "order": "1"},
                    {"name": "Actor Two", "character": "Villain", "order": "2"},
                ],
                "crew": [],
            },
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        # Verify people created
        people_count = int(conn.execute("SELECT COUNT(*) FROM people").fetchone()[0])
        assert people_count == 2

        # Verify movie_people relationships
        rels = conn.execute("SELECT COUNT(*) FROM movie_people").fetchone()[0]
        assert rels == 2

    def test_people_are_deduplicated(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Movie.2024.1080p.mkv").write_bytes(b"")
        (tmp / "Movie.2024.720p.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Movie", "media_type": "movie",
                 "vote_average": 7.0, "year": 2024,
                 "poster_path": None, "backdrop_path": None}
            ],
            details={
                "id": 1, "title": "Movie", "release_date": "2024-01-01",
                "overview": "Plot", "genres": [],
                "poster_path": None, "backdrop_path": None,
            },
            external_ids={"imdb_id": "tt001"},
            credits={
                "cast": [
                    {"name": "Same Actor", "character": "Role", "order": "1", "id": 42},
                ],
                "crew": [],
            },
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        # Same actor should only be created once
        people_count = int(conn.execute("SELECT COUNT(*) FROM people").fetchone()[0])
        assert people_count == 1


class TestTmdbCreditsContract:
    """Regression tests for TMDB credits → people persistence contract."""

    def test_person_id_used_not_order(self) -> None:
        """TMDB person['id'] is used for tmdb_id, NOT cast 'order'."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Movie.2024.1080p.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Movie", "media_type": "movie",
                 "vote_average": 7.0, "year": 2024,
                 "poster_path": None, "backdrop_path": None}
            ],
            details={
                "id": 1, "title": "Movie", "release_date": "2024-01-01",
                "overview": "Plot", "genres": [],
                "poster_path": None, "backdrop_path": None,
            },
            external_ids={"imdb_id": "tt001"},
            credits={
                "cast": [
                    # TMDB returns person["id"] = 999, but cast "order" = 1
                    {"name": "Actor One", "character": "Hero", "order": "1", "id": 999},
                ],
                "crew": [],
            },
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        # Person should have tmdb_id=999, NOT tmdb_id=1 (which is cast order)
        person = conn.execute("SELECT tmdb_id FROM people").fetchone()
        assert person is not None
        assert person["tmdb_id"] == 999, f"Expected tmdb_id=999, got {person['tmdb_id']}"

    def test_credits_with_cast_and_crew(self) -> None:
        """Both cast and crew from TMDB credits object are processed."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Movie.2024.1080p.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Movie", "media_type": "movie",
                 "vote_average": 7.0, "year": 2024,
                 "poster_path": None, "backdrop_path": None}
            ],
            details={
                "id": 1, "title": "Movie", "release_date": "2024-01-01",
                "overview": "Plot", "genres": [],
                "poster_path": None, "backdrop_path": None,
            },
            external_ids={"imdb_id": "tt001"},
            credits={
                "cast": [
                    {"name": "Actor", "character": "Hero", "order": "1", "id": 10},
                ],
                "crew": [
                    {"name": "Director", "job": "Director", "department": "Directing", "id": 20},
                ],
            },
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        people_count = int(conn.execute("SELECT COUNT(*) FROM people").fetchone()[0])
        assert people_count == 2  # 1 cast + 1 crew

    def test_no_fake_imdb_ids_from_credits(self) -> None:
        """Cast/crew data does not fabricate IMDb IDs."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Movie.2024.1080p.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Movie", "media_type": "movie",
                 "vote_average": 7.0, "year": 2024,
                 "poster_path": None, "backdrop_path": None}
            ],
            details={
                "id": 1, "title": "Movie", "release_date": "2024-01-01",
                "overview": "Plot", "genres": [],
                "poster_path": None, "backdrop_path": None,
            },
            external_ids={"imdb_id": "tt001"},
            credits={
                "cast": [
                    {"name": "Actor", "character": "Hero", "order": "1", "id": 10},
                ],
                "crew": [],
            },
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        # People should have no IMDb ID (TMDB credits don't provide them)
        people = conn.execute("SELECT imdb_id FROM people").fetchall()
        for p in people:
            assert p["imdb_id"] is None

    def test_no_duplicate_people_same_tmdb_id(self) -> None:
        """Same TMDB person across multiple files creates only one people row."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Movie.2024.1080p.mkv").write_bytes(b"")
        (tmp / "Movie.2024.720p.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(
            search_hits=[
                {"id": 1, "title": "Movie", "media_type": "movie",
                 "vote_average": 7.0, "year": 2024,
                 "poster_path": None, "backdrop_path": None}
            ],
            details={
                "id": 1, "title": "Movie", "release_date": "2024-01-01",
                "overview": "Plot", "genres": [],
                "poster_path": None, "backdrop_path": None,
            },
            external_ids={"imdb_id": "tt001"},
            credits={
                "cast": [
                    {"name": "Same Actor", "character": "Role", "order": "1", "id": 55},
                ],
                "crew": [],
            },
        )

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        people_count = int(conn.execute("SELECT COUNT(*) FROM people").fetchone()[0])
        assert people_count == 1
        person = conn.execute("SELECT tmdb_id FROM people").fetchone()
        assert person["tmdb_id"] == 55


class TestTmdbDiscoverySelection:
    """Regression tests for discovery result selection logic."""

    def test_prefers_exact_year_match(self) -> None:
        """When year is known, exact-year match is preferred over higher vote."""
        provider = _mock_tmdb_provider(search_hits=[
            {"id": 1, "title": "Show A", "media_type": "tv",
             "vote_average": 9.5, "year": 2019,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2019-01-01"},
            {"id": 2, "title": "Show B", "media_type": "tv",
             "vote_average": 8.0, "year": 2020,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2020-01-01"},
        ])
        results = provider.search(entity_type="tv", query="Show", year=2020)
        assert len(results) >= 2
        assert results[0]["id"] == 2  # year 2020 match first

    def test_fallback_to_highest_vote(self) -> None:
        """When no exact year match, highest vote_average wins."""
        provider = _mock_tmdb_provider(search_hits=[
            {"id": 1, "title": "Show A", "media_type": "tv",
             "vote_average": 9.5, "year": 2019,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2019-01-01"},
            {"id": 2, "title": "Show B", "media_type": "tv",
             "vote_average": 8.0, "year": 2020,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2020-01-01"},
        ])
        results = provider.search(entity_type="tv", query="Show", year=2025)
        assert len(results) >= 2
        assert results[0]["id"] == 1  # no year match, highest vote wins

    def test_discover_uses_year_priority(self) -> None:
        """LibraryMetadataIntegration._discover selects exact year match."""
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.2020.1080p.mkv").write_bytes(b"")

        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        provider = _mock_tmdb_provider(search_hits=[
            {"id": 1, "title": "Other Show", "media_type": "tv",
             "vote_average": 9.5, "year": 2019,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2019-01-01"},
            {"id": 2, "title": "My Show", "media_type": "tv",
             "vote_average": 7.0, "year": 2020,
             "poster_path": None, "backdrop_path": None,
             "first_air_date": "2020-01-01"},
        ])

        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        # The identifier produces year=2020 from the filename
        sr = ScanResult(
            path=Path(tmp / "Show.S01E01.2020.1080p.mkv"),
            filename="Show.S01E01.2020.1080p.mkv",
            extension=".mkv",
            size_bytes=1000,
        )
        id_result = identify(sr)
        discovered = integration._discover(id_result, "tv")
        assert discovered is not None
        assert discovered["external_id"] == "2"  # year 2020 match


class TestTmdbExternalIds:
    """Verify external ID persistence."""

    def test_tmdb_id_persisted(self) -> None:
        conn = _connection()
        provider = _mock_tmdb_provider(
            details={"id": 42, "title": "Movie", "release_date": "2024-01-01",
                     "overview": "", "genres": [], "poster_path": None,
                     "backdrop_path": None},
            external_ids={"imdb_id": "tt42"},
            credits={"cast": [], "crew": []},
        )
        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)

        result = IdentificationResult(
            media_type=MediaType.MOVIE, title="Movie", year=2024,
            provider="tmdb", external_id="42",
        )
        meta_svc.resolve_identification(result)
        meta_svc.fetch_and_save_metadata(
            entity_type="movie", entity_id=1, external_id="42",
            provider_name="tmdb",
        )

        row = conn.execute("SELECT * FROM movies WHERE id = 1").fetchone()
        assert row["tmdb_id"] == 42

        eids = meta_repo.list_external_ids("movie", 1)
        providers = {e["provider"] for e in eids}
        assert "tmdb" in providers
        assert "imdb" in providers

    def test_duplicate_external_id_reuses_entity(self) -> None:
        conn = _connection()
        provider = _mock_tmdb_provider(
            details={"id": 42, "title": "Movie", "release_date": "2024-01-01",
                     "overview": "", "genres": [], "poster_path": None,
                     "backdrop_path": None},
            external_ids={"imdb_id": "tt42"},
            credits={"cast": [], "crew": []},
        )
        registry = MetadataProviderRegistry()
        registry.register(provider)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)

        r1 = IdentificationResult(
            media_type=MediaType.MOVIE, title="Movie", year=2024,
            provider="tmdb", external_id="42",
        )
        r2 = IdentificationResult(
            media_type="movie", title="Movie Again", year=2024,
            provider="tmdb", external_id="42",
        )
        res1 = meta_svc.resolve_identification(r1)
        res2 = meta_svc.resolve_identification(r2)
        assert res1.entity_id == res2.entity_id
        assert res2.created is False


class TestTmdbMissingKey:
    """Verify graceful degradation when TMDB key is unavailable."""

    def test_pipeline_works_without_tmdb_key(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")

        conn = _connection()
        repo = LibraryRepository(conn)
        repo.add_location(tmp, label=str(tmp))
        conn.commit()
        sync_location(conn, tmp)

        # No TMDB provider registered (empty key)
        registry = MetadataProviderRegistry()
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo, registry=registry)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf in conn.execute("SELECT * FROM media_files").fetchall():
            sr = ScanResult(
                path=Path(mf["path"]),
                filename=mf["filename"],
                extension=mf["extension"],
                size_bytes=mf["size_bytes"],
            )
            integration.process_identification(identify(sr))

        tv_shows = int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0])
        assert tv_shows == 1

    def test_metadata_fetched_false_without_provider(self) -> None:
        conn = _connection()
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo)
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        music_svc = MusicService(MusicRepository(conn))
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        result = IdentificationResult(
            media_type=MediaType.MOVIE, title="Local Movie", year=2024,
            confidence=0.8,
        )
        lib_result = integration.process_identification(result)
        assert lib_result.metadata_fetched is False
        assert lib_result.resolution.entity_type == "movie"
        assert lib_result.resolution.created is True
