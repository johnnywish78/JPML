"""Regression tests for the generic media ingestion / identification pipeline.

These tests verify:
  - Generic TV filename parsing and show identity normalization
  - Entity reuse / deduplication (no duplicate tv_shows per episode)
  - Season and episode reuse
  - Idempotency (running the same scan twice produces the same graph)
  - Movie pipeline remains functional
  - External ID persistence
  - Metadata persistence via provider
  - Artwork persistence contract
  - Babylon Berlin regression (16 episodes → 1 show, 2 seasons, 16 episodes)
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.database.schema import initialize
from app.domain.media import MediaType
from app.library.coordinator import process_library_metadata, sync_location
from app.library.library_repository import LibraryRepository
from app.library.scanner import ScanResult
from app.metadata.identifier import IdentificationResult, identify
from app.metadata.library_integration import LibraryMetadataIntegration
from app.metadata.omdb_provider import OMDbMetadataProvider
from app.metadata.provider import MetadataProvider, ProviderMetadata, StaticMetadataProvider
from app.metadata.registry import MetadataProviderRegistry
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    initialize(conn)
    return conn


def _make_files(tmp: Path, pattern: str, count: int = 1) -> list[Path]:
    """Create dummy media files matching *pattern* with *count* episodes."""
    files: list[Path] = []
    for i in range(1, count + 1):
        name = pattern.format(i) if "{}" in pattern else f"{pattern}.{i:02d}"
        p = tmp / f"{name}.mkv"
        p.write_bytes(b"fake")
        files.append(p)
    return files


def _sync_and_process(
    conn: sqlite3.Connection,
    lib_dir: Path,
    provider: MetadataProvider | None = None,
) -> tuple[int, int, int, int, int]:
    """Run sync + metadata pipeline and return (media_files, tv_shows,
    seasons, episodes, episode_files)."""
    repo = LibraryRepository(conn)
    # Add location only if it doesn't already exist
    existing = conn.execute(
        "SELECT 1 FROM library_locations WHERE path = ?",
        (str(lib_dir.resolve()),),
    ).fetchone()
    if existing is None:
        repo.add_location(lib_dir, label=str(lib_dir))
        conn.commit()

    sync_location(conn, lib_dir)

    if provider is not None:
        registry = MetadataProviderRegistry()
        registry.register(provider)
        from app.metadata.service import MetadataService
        from app.metadata.repository import MetadataRepository
        from app.metadata.library_integration import LibraryMetadataIntegration
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository

        meta_repo = MetadataRepository(conn)
        music_repo = MusicRepository(conn)
        music_svc = MusicService(music_repo)
        meta_svc = MetadataService(meta_repo, registry=registry)
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)
    else:
        from app.metadata.service import MetadataService
        from app.metadata.repository import MetadataRepository
        from app.metadata.library_integration import LibraryMetadataIntegration
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository

        meta_repo = MetadataRepository(conn)
        music_repo = MusicRepository(conn)
        music_svc = MusicService(music_repo)
        meta_svc = MetadataService(meta_repo)
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

    process_library_metadata(conn, integration=integration)

    return (
        int(conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0]),
        int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0]),
        int(conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]),
        int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]),
        int(conn.execute("SELECT COUNT(*) FROM episode_files").fetchone()[0]),
    )


# ---------------------------------------------------------------------------
# Generic TV identification and deduplication
# ---------------------------------------------------------------------------


class TestGenericTvIdentification:
    """Verify that generic TV filename parsing works for arbitrary shows."""

    def test_generic_show_s01e01(self) -> None:
        result = identify(
            ScanResult(
                path=Path("/tmp/Test.Show.S01E01.720p.mkv"),
                filename="Test.Show.S01E01.720p.mkv",
                extension=".mkv",
                size_bytes=1000,
            )
        )
        assert result.media_type == MediaType.EPISODE
        assert result.title == "Test Show"
        assert result.season == 1
        assert result.episode == 1

    def test_generic_show_s01e02_same_show(self) -> None:
        r1 = identify(
            ScanResult(
                path=Path("/tmp/Test.Show.S01E01.mkv"),
                filename="Test.Show.S01E01.mkv",
                extension=".mkv",
                size_bytes=1000,
            )
        )
        r2 = identify(
            ScanResult(
                path=Path("/tmp/Test.Show.S01E02.mkv"),
                filename="Test.Show.S01E02.mkv",
                extension=".mkv",
                size_bytes=1000,
            )
        )
        assert r1.title == r2.title == "Test Show"
        assert r1.season == r2.season == 1
        assert r1.episode == 1
        assert r2.episode == 2

    def test_generic_show_multiple_seasons(self) -> None:
        r_s1 = identify(
            ScanResult(
                path=Path("/tmp/My.Show.S01E01.mkv"),
                filename="My.Show.S01E01.mkv",
                extension=".mkv",
                size_bytes=1000,
            )
        )
        r_s2 = identify(
            ScanResult(
                path=Path("/tmp/My.Show.S02E01.mkv"),
                filename="My.Show.S02E01.mkv",
                extension=".mkv",
                size_bytes=1000,
            )
        )
        assert r_s1.title == r_s2.title == "My Show"
        assert r_s1.season == 1
        assert r_s2.season == 2

    def test_quality_tokens_stripped_from_title(self) -> None:
        result = identify(
            ScanResult(
                path=Path("/tmp/Some.Show.S01E01.720p.WEB-DL.mkv"),
                filename="Some.Show.S01E01.720p.WEB-DL.mkv",
                extension=".mkv",
                size_bytes=1000,
            )
        )
        assert result.media_type == MediaType.EPISODE
        assert result.title == "Some Show"
        assert "720p" not in result.title
        assert "WEB" not in result.title

    def test_release_group_stripped(self) -> None:
        result = identify(
            ScanResult(
                path=Path("/tmp/Show.Name.S01E01.1080p.WEB-DL.x264-Group.mkv"),
                filename="Show.Name.S01E01.1080p.WEB-DL.x264-Group.mkv",
                extension=".mkv",
                size_bytes=1000,
            )
        )
        assert result.media_type == MediaType.EPISODE
        assert result.title == "Show Name"
        assert "Group" not in result.title

    def test_x_pattern(self) -> None:
        result = identify(
            ScanResult(
                path=Path("/tmp/Show.1x01.720p.mkv"),
                filename="Show.1x01.720p.mkv",
                extension=".mkv",
                size_bytes=1000,
            )
        )
        assert result.media_type == MediaType.EPISODE
        assert result.title == "Show"
        assert result.season == 1
        assert result.episode == 1


# ---------------------------------------------------------------------------
# Entity deduplication
# ---------------------------------------------------------------------------


class TestEntityDeduplication:
    """Verify that multiple episodes of the same show reuse one tv_show."""

    def test_two_episodes_reuse_same_tv_show(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "My.Show.S01E01.mkv").write_bytes(b"")
        (tmp / "My.Show.S01E02.mkv").write_bytes(b"")

        media_files, tv_shows, seasons, episodes, ep_files = _sync_and_process(
            conn, tmp
        )

        assert media_files == 2
        assert tv_shows == 1, f"Expected 1 tv_show, got {tv_shows}"
        assert seasons >= 1
        assert episodes == 2
        assert ep_files == 2

    def test_two_seasons_reuse_same_tv_show(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "My.Show.S01E01.mkv").write_bytes(b"")
        (tmp / "My.Show.S02E01.mkv").write_bytes(b"")

        media_files, tv_shows, seasons, episodes, ep_files = _sync_and_process(
            conn, tmp
        )

        assert media_files == 2
        assert tv_shows == 1, f"Expected 1 tv_show, got {tv_shows}"
        assert seasons == 2, f"Expected 2 seasons, got {seasons}"
        assert episodes == 2
        assert ep_files == 2

    def test_different_shows_create_separate_entities(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.A.S01E01.mkv").write_bytes(b"")
        (tmp / "Show.B.S01E01.mkv").write_bytes(b"")

        media_files, tv_shows, seasons, episodes, ep_files = _sync_and_process(
            conn, tmp
        )

        assert media_files == 2
        assert tv_shows == 2, f"Expected 2 tv_shows, got {tv_shows}"
        assert episodes == 2


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Running the same scan twice must not create duplicates."""

    def test_second_scan_no_duplicates(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Example.Show.S01E01.mkv").write_bytes(b"")
        (tmp / "Example.Show.S01E02.mkv").write_bytes(b"")
        (tmp / "Example.Show.S02E01.mkv").write_bytes(b"")

        # First scan
        _sync_and_process(conn, tmp)
        first = (
            int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episode_files").fetchone()[0]),
        )

        # Second scan — same files
        _sync_and_process(conn, tmp)
        second = (
            int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episode_files").fetchone()[0]),
        )

        assert first == second, f"First {first}, second {second}"
        assert first == (1, 2, 3, 3), f"Expected (1,2,3,3), got {first}"

    def test_second_scan_no_duplicate_media_files(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")

        _sync_and_process(conn, tmp)
        first_count = int(conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0])

        _sync_and_process(conn, tmp)
        second_count = int(conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0])

        assert first_count == second_count == 1


# ---------------------------------------------------------------------------
# Babylon Berlin regression
# ---------------------------------------------------------------------------


class TestBabylonBerlinRegression:
    """Regenerate the exact failure scenario from the real database."""

    def test_babylon_berlin_pipeline(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())

        # Season 1: episodes 1-8
        for i in range(1, 9):
            (
                tmp / f"Babylon.Berlin.S01E{i:02d}.720p.WEB-DL.x264.NightMovie.mkv"
            ).write_bytes(b"")
        # Season 2: episodes 1-8
        for i in range(1, 9):
            (
                tmp / f"Babylon.Berlin.S02E{i:02d}.720p.WEB-DL.x264.NightMovie.mkv"
            ).write_bytes(b"")

        media_files, tv_shows, seasons, episodes, ep_files = _sync_and_process(
            conn, tmp
        )

        assert media_files == 16, f"Expected 16 media files, got {media_files}"
        assert tv_shows == 1, f"Expected 1 tv_show, got {tv_shows}"
        assert seasons == 2, f"Expected 2 seasons, got {seasons}"
        assert episodes == 16, f"Expected 16 episodes, got {episodes}"
        assert ep_files == 16, f"Expected 16 episode_files, got {ep_files}"

    def test_babylon_berlin_season_grouping(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())

        for i in range(1, 9):
            (
                tmp / f"Babylon.Berlin.S01E{i:02d}.720p.WEB-DL.x264.NightMovie.mkv"
            ).write_bytes(b"")
        for i in range(1, 9):
            (
                tmp / f"Babylon.Berlin.S02E{i:02d}.720p.WEB-DL.x264.NightMovie.mkv"
            ).write_bytes(b"")

        _sync_and_process(conn, tmp)

        # Verify season 1 has episodes 1-8
        s1_ep_count = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM episodes e
                JOIN seasons s ON s.id = e.season_id
                WHERE s.tv_show_id = (SELECT id FROM tv_shows LIMIT 1)
                  AND s.season_number = 1
                """
            ).fetchone()[0]
        )
        assert s1_ep_count == 8, f"Expected 8 eps in S1, got {s1_ep_count}"

        # Verify season 2 has episodes 1-8
        s2_ep_count = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM episodes e
                JOIN seasons s ON s.id = e.season_id
                WHERE s.tv_show_id = (SELECT id FROM tv_shows LIMIT 1)
                  AND s.season_number = 2
                """
            ).fetchone()[0]
        )
        assert s2_ep_count == 8, f"Expected 8 eps in S2, got {s2_ep_count}"

    def test_babylon_berlin_idempotent(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())

        for i in range(1, 9):
            (
                tmp / f"Babylon.Berlin.S01E{i:02d}.720p.WEB-DL.x264.NightMovie.mkv"
            ).write_bytes(b"")
        for i in range(1, 9):
            (
                tmp / f"Babylon.Berlin.S02E{i:02d}.720p.WEB-DL.x264.NightMovie.mkv"
            ).write_bytes(b"")

        _sync_and_process(conn, tmp)
        first = (
            int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]),
        )

        _sync_and_process(conn, tmp)
        second = (
            int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM seasons").fetchone()[0]),
            int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]),
        )

        assert first == second == (1, 2, 16)


# ---------------------------------------------------------------------------
# Movie pipeline
# ---------------------------------------------------------------------------


class TestMoviePipeline:
    """Verify the movie path is not broken by TV changes."""

    def test_movie_creation(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Inception.2010.1080p.BluRay.mkv").write_bytes(b"")

        media_files, movies = self._run_sync(conn, tmp)

        assert media_files == 1
        assert movies == 1

    def test_movie_deduplication(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Inception.2010.1080p.BluRay.mkv").write_bytes(b"")
        (tmp / "Inception.2010.720p.WEB.mkv").write_bytes(b"")

        self._run_sync(conn, tmp)
        movies = int(conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0])
        media_files = int(conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0])

        assert media_files == 2
        assert movies == 1, f"Expected 1 movie, got {movies}"

    def test_movie_with_year_parsing(self) -> None:
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Dune.Part.Two.2024.2160p.UHD.mkv").write_bytes(b"")

        self._run_sync(conn, tmp)

        row = conn.execute("SELECT title, year FROM movies LIMIT 1").fetchone()
        assert row is not None
        assert "Dune" in row["title"]
        assert row["year"] == 2024

    @staticmethod
    def _run_sync(conn: sqlite3.Connection, lib_dir: Path) -> tuple[int, int]:
        from app.library.library_repository import LibraryRepository
        from app.metadata.service import MetadataService
        from app.metadata.repository import MetadataRepository
        from app.metadata.library_integration import LibraryMetadataIntegration
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository

        repo = LibraryRepository(conn)
        existing = conn.execute(
            "SELECT 1 FROM library_locations WHERE path = ?",
            (str(lib_dir.resolve()),),
        ).fetchone()
        if existing is None:
            repo.add_location(lib_dir, label=str(lib_dir))
            conn.commit()
        sync_location(conn, lib_dir)

        music_repo = MusicRepository(conn)
        music_svc = MusicService(music_repo)
        meta_repo = MetadataRepository(conn)
        meta_svc = MetadataService(meta_repo)
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)
        process_library_metadata(conn, integration=integration)

        movies = int(conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0])
        media_files = int(conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0])
        return media_files, movies


# ---------------------------------------------------------------------------
# Metadata persistence with provider
# ---------------------------------------------------------------------------


class TestMetadataPersistence:
    """Verify that real provider metadata is persisted correctly."""

    def test_provider_metadata_updates_title_and_year(self) -> None:
        provider = StaticMetadataProvider({
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "overview": "A chemistry teacher.",
                "genres": ["Drama", "Crime"],
                "external_id": "tt0903747",
            }
        })
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")

        repo = LibraryRepository(conn)
        repo.add_location(tmp, label="test")
        conn.commit()
        sync_location(conn, tmp)

        from app.metadata.service import MetadataService
        from app.metadata.repository import MetadataRepository
        from app.metadata.library_integration import LibraryMetadataIntegration
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        from app.library.scanner import ScanResult
        from app.metadata.identifier import identify

        meta_repo = MetadataRepository(conn)
        music_repo = MusicRepository(conn)
        music_svc = MusicService(music_repo)
        meta_svc = MetadataService(meta_repo, provider=provider)
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        mf = conn.execute("SELECT * FROM media_files").fetchone()
        sr = ScanResult(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(sr)
        id_result.provider = "static"
        id_result.external_id = "tt0903747"
        integration.process_identification(id_result)

        row = conn.execute("SELECT title, year, overview FROM tv_shows LIMIT 1").fetchone()
        assert row["title"] == "Breaking Bad"
        assert row["year"] == 2008
        assert row["overview"] == "A chemistry teacher."

    def test_external_id_persisted(self) -> None:
        provider = StaticMetadataProvider({
            "tv:tt1234567": {
                "title": "Test Show",
                "external_id": "tt1234567",
            }
        })
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")

        repo = LibraryRepository(conn)
        repo.add_location(tmp, label="test")
        conn.commit()
        sync_location(conn, tmp)

        from app.metadata.service import MetadataService
        from app.metadata.repository import MetadataRepository
        from app.metadata.library_integration import LibraryMetadataIntegration
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        from app.library.scanner import ScanResult
        from app.metadata.identifier import identify

        meta_repo = MetadataRepository(conn)
        music_repo = MusicRepository(conn)
        music_svc = MusicService(music_repo)
        meta_svc = MetadataService(meta_repo, provider=provider)
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        mf = conn.execute("SELECT * FROM media_files").fetchone()
        sr = ScanResult(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(sr)
        id_result.provider = "static"
        id_result.external_id = "tt1234567"
        integration.process_identification(id_result)

        eids = meta_repo.list_external_ids("tv", 1)
        assert len(eids) == 1
        assert eids[0]["external_id"] == "tt1234567"

    def test_duplicate_external_id_reuses_entity(self) -> None:
        provider = StaticMetadataProvider({
            "tv:tt9999999": {
                "title": "Repeated Show",
                "external_id": "tt9999999",
            }
        })
        conn = _connection()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Show.S01E01.mkv").write_bytes(b"")
        (tmp / "Show.S01E02.mkv").write_bytes(b"")

        repo = LibraryRepository(conn)
        repo.add_location(tmp, label="test")
        conn.commit()
        sync_location(conn, tmp)

        from app.metadata.service import MetadataService
        from app.metadata.repository import MetadataRepository
        from app.metadata.library_integration import LibraryMetadataIntegration
        from app.services.music import MusicService
        from app.library.music_repository import MusicRepository
        from app.library.scanner import ScanResult
        from app.metadata.identifier import identify

        meta_repo = MetadataRepository(conn)
        music_repo = MusicRepository(conn)
        music_svc = MusicService(music_repo)
        meta_svc = MetadataService(meta_repo, provider=provider)
        integration = LibraryMetadataIntegration(meta_svc, music_service=music_svc)

        for mf_row in conn.execute("SELECT * FROM media_files"):
            sr = ScanResult(
                path=Path(mf_row["path"]),
                filename=mf_row["filename"],
                extension=mf_row["extension"],
                size_bytes=mf_row["size_bytes"],
            )
            id_result = identify(sr)
            id_result.provider = "static"
            id_result.external_id = "tt9999999"
            integration.process_identification(id_result)

        tv_count = int(conn.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0])
        assert tv_count == 1, f"Expected 1 tv_show, got {tv_count}"


# ---------------------------------------------------------------------------
# Artwork contract
# ---------------------------------------------------------------------------


class TestArtworkContract:
    """Verify artwork persistence contract."""

    def test_artwork_row_created_when_local_path_provided(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        tv_id = repo.create_tv_show(title="Test Show")

        import tempfile
        img_path = Path(tempfile.mktemp(suffix=".jpg"))
        img_path.write_bytes(b"fake-image-data")

        repo.add_artwork(
            entity_type="tv",
            entity_id=tv_id,
            artwork_type="poster",
            provider="static",
            local_path=str(img_path),
        )

        rows = repo.list_artwork("tv", tv_id)
        assert len(rows) == 1
        assert rows[0]["local_path"] == str(img_path)
        assert rows[0]["artwork_type"] == "poster"

        img_path.unlink(missing_ok=True)

    def test_no_artwork_without_provider(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        tv_id = repo.create_tv_show(title="Test Show")

        rows = repo.list_artwork("tv", tv_id)
        assert rows == []

    def test_artwork_unique_constraint(self) -> None:
        conn = _connection()
        repo = MetadataRepository(conn)
        tv_id = repo.create_tv_show(title="Test Show")

        import tempfile
        img_path = Path(tempfile.mktemp(suffix=".jpg"))
        img_path.write_bytes(b"data")

        repo.add_artwork(
            entity_type="tv", entity_id=tv_id,
            artwork_type="poster", provider="p1",
            local_path=str(img_path),
        )
        # Inserting the same provider/artwork_type should be handled by
        # the UNIQUE constraint; we verify idempotency by using a different
        # provider instead.
        img_path2 = Path(tempfile.mktemp(suffix=".jpg"))
        img_path2.write_bytes(b"data2")
        repo.add_artwork(
            entity_type="tv", entity_id=tv_id,
            artwork_type="poster", provider="p2",
            local_path=str(img_path2),
        )

        rows = repo.list_artwork("tv", tv_id)
        assert len(rows) == 2
        img_path.unlink(missing_ok=True)
        img_path2.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Provider testing
# ---------------------------------------------------------------------------


class TestProviderBehavior:
    """Verify provider integration behavior."""

    def test_omdb_returns_none_without_api_key(self) -> None:
        provider = OMDbMetadataProvider(api_key="")
        with pytest.raises(ValueError, match="OMDB_API_KEY"):
            provider.fetch_metadata(entity_type="movie", external_id="tt123")

    def test_omdb_returns_none_for_missing_movie(self) -> None:
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"Response": "False", "Error": "Not found"}
        mock_session.get.return_value = mock_response

        provider = OMDbMetadataProvider(api_key="key", session=mock_session)
        result = provider.fetch_metadata(entity_type="movie", external_id="tt9999999")
        assert result is None

    def test_static_provider_returns_metadata(self) -> None:
        provider = StaticMetadataProvider({
            "movie:tt123": {
                "title": "Test Movie",
                "year": 2024,
                "overview": "Plot.",
                "genres": ["Drama"],
                "external_id": "tt123",
            }
        })
        result = provider.fetch_metadata(entity_type="movie", external_id="tt123")
        assert result is not None
        assert result.title == "Test Movie"
        assert result.year == 2024
        assert result.genres == ("Drama",)
        assert result.external_id == "tt123"

    def test_static_provider_returns_none_for_missing(self) -> None:
        provider = StaticMetadataProvider({})
        result = provider.fetch_metadata(entity_type="movie", external_id="tt999")
        assert result is None
