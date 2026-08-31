from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.database.schema import initialize
from app.domain.media import MediaType
from app.library.coordinator import sync_location, process_library_metadata
from app.library.media_repository import MediaRepository
from app.metadata.library_integration import LibraryMetadataIntegration
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


class TestLibraryPipelineMovie:
    def test_movie_file_enters_pipeline(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "Dreams.",
                "genres": ["Sci-Fi", "Action"],
                "external_id": "tt1375666",
            }
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        sync_result = sync_location(conn, lib_dir)
        assert sync_result.files_added == 1

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        proc_result = process_library_metadata(conn, integration=integration)

        assert proc_result.files_processed == 1
        assert proc_result.entities_created == 1
        assert proc_result.errors == []

        movies = conn.execute("SELECT * FROM movies").fetchall()
        assert len(movies) == 1
        assert movies[0]["title"] == "Inception (2010)" or "Inception" in movies[0]["title"]

    def test_movie_with_imdb_id_full_pipeline(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "overview": "A dream within a dream.",
                "genres": ["Sci-Fi", "Action", "Thriller"],
                "external_id": "tt1375666",
            }
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["Movies"])
        id_result.provider = "static"
        id_result.external_id = "tt1375666"

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

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

    def test_tv_file_full_pipeline(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "TV"
        lib_dir.mkdir()
        (lib_dir / "Breaking.Bad.S01E01.720p.mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "overview": "Chemistry teacher.",
                "genres": ["Drama", "Crime"],
                "external_id": "tt0903747",
            }
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["TV Shows", "Breaking Bad"])

        assert id_result.media_type == MediaType.EPISODE

        id_result.provider = "static"
        id_result.external_id = "tt0903747"

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        lib_result = integration.process_identification(id_result)

        assert lib_result.resolution.entity_type == "tv"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is True

        entity_id = lib_result.resolution.entity_id
        genres = repo.get_tv_genres(entity_id)
        assert "Drama" in genres
        assert "Crime" in genres


class TestLibraryPipelineIdempotent:
    def test_second_processing_reuses_entity(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "genres": ["Sci-Fi"],
                "external_id": "tt1375666",
            }
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["Movies"])
        id_result.provider = "static"
        id_result.external_id = "tt1375666"

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        res1 = integration.process_identification(id_result)
        res2 = integration.process_identification(id_result)

        assert res1.resolution.entity_id == res2.resolution.entity_id
        assert res2.resolution.created is False

        eids = repo.list_external_ids("movie", res1.resolution.entity_id)
        assert len(eids) == 1

    def test_second_scan_idempotent(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)
        assert MediaRepository(conn).count() == 1

        sync_location(conn, lib_dir)
        assert MediaRepository(conn).count() == 1


class TestLibraryPipelineProviderFailure:
    def test_provider_failure_does_not_corrupt(self, tmp_path: Path) -> None:
        class FailingProvider(MetadataProvider):
            name = "failing"

            def fetch_metadata(self, *, entity_type: str, external_id: str):
                raise ConnectionError("network down")

        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Test Movie.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["Movies"])
        id_result.provider = "failing"
        id_result.external_id = "tt999"

        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=FailingProvider())
        integration = LibraryMetadataIntegration(service)

        lib_result = integration.process_identification(id_result)

        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is False

        entity_id = lib_result.resolution.entity_id
        eids = repo.list_external_ids("movie", entity_id)
        assert len(eids) == 1

    def test_no_provider_still_creates_entity(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Local Movie.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["Movies"])

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        lib_result = integration.process_identification(id_result)

        assert lib_result.resolution.entity_type == "movie"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is False


class TestLibraryPipelineNoExternalId:
    def test_movie_without_external_id(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Original Movie.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["Movies"])

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        lib_result = integration.process_identification(id_result)

        assert lib_result.resolution.entity_type == "movie"
        assert lib_result.resolution.created is True
        assert lib_result.metadata_fetched is False

        entity_id = lib_result.resolution.entity_id
        eids = repo.list_external_ids("movie", entity_id)
        assert eids == []


class TestLibraryPipelineMediaFileLinking:
    def test_media_file_linked_to_movie(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Test Movie.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["Movies"])

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        lib_result = integration.process_identification(id_result)

        from app.library.coordinator import _link_media_file

        _link_media_file(
            connection=conn,
            media_file_id=mf["id"],
            entity_type=lib_result.resolution.entity_type,
            entity_id=lib_result.resolution.entity_id,
        )

        links = conn.execute("SELECT * FROM movie_files").fetchall()
        assert len(links) == 1
        assert links[0]["movie_id"] == lib_result.resolution.entity_id
        assert links[0]["media_file_id"] == mf["id"]

    def test_media_file_linked_to_tv(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "TV"
        lib_dir.mkdir()
        (lib_dir / "Show.S01E01.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["TV Shows"])

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        lib_result = integration.process_identification(id_result)

        from app.library.coordinator import _link_media_file

        _link_media_file(
            connection=conn,
            media_file_id=mf["id"],
            entity_type=lib_result.resolution.entity_type,
            entity_id=lib_result.resolution.entity_id,
            season=id_result.season,
            episode=id_result.episode,
        )

        seasons = conn.execute("SELECT * FROM seasons").fetchall()
        assert len(seasons) == 1
        assert seasons[0]["season_number"] == 1

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        assert len(episodes) == 1
        assert episodes[0]["episode_number"] == 1

        ep_links = conn.execute("SELECT * FROM episode_files").fetchall()
        assert len(ep_links) == 1


class TestTVLinkingActualSeasonEpisode:
    def test_s02e05_creates_correct_season_episode(self) -> None:
        from app.library.coordinator import _link_tv_media_file

        conn = _connection()
        conn.execute("INSERT INTO tv_shows(title) VALUES (?)", ("Test Show",))
        tv_id = conn.execute("SELECT id FROM tv_shows").fetchone()["id"]
        conn.execute(
            "INSERT INTO media_files(path, filename, extension) VALUES (?, ?, ?)",
            ("/tmp/test.mkv", "test.mkv", ".mkv"),
        )
        mf_id = conn.execute("SELECT id FROM media_files").fetchone()["id"]

        _link_tv_media_file(
            connection=conn,
            tv_show_id=tv_id,
            media_file_id=mf_id,
            season=2,
            episode=5,
        )

        seasons = conn.execute(
            "SELECT * FROM seasons WHERE tv_show_id = ?", (tv_id,)
        ).fetchall()
        assert len(seasons) == 1
        assert seasons[0]["season_number"] == 2

        episodes = conn.execute(
            "SELECT * FROM episodes WHERE season_id = ?", (seasons[0]["id"],)
        ).fetchall()
        assert len(episodes) == 1
        assert episodes[0]["episode_number"] == 5

    def test_multiple_episodes_different_seasons(self) -> None:
        from app.library.coordinator import _link_tv_media_file

        conn = _connection()
        conn.execute("INSERT INTO tv_shows(title) VALUES (?)", ("Test Show",))
        tv_id = conn.execute("SELECT id FROM tv_shows").fetchone()["id"]

        for i in range(1, 4):
            conn.execute(
                "INSERT INTO media_files(path, filename, extension) VALUES (?, ?, ?)",
                (f"/tmp/test{i}.mkv", f"test{i}.mkv", ".mkv"),
            )
        mf_ids = [r["id"] for r in conn.execute("SELECT id FROM media_files ORDER BY id").fetchall()]

        _link_tv_media_file(
            connection=conn,
            tv_show_id=tv_id,
            media_file_id=mf_ids[0],
            season=1,
            episode=1,
        )
        _link_tv_media_file(
            connection=conn,
            tv_show_id=tv_id,
            media_file_id=mf_ids[1],
            season=1,
            episode=2,
        )
        _link_tv_media_file(
            connection=conn,
            tv_show_id=tv_id,
            media_file_id=mf_ids[2],
            season=2,
            episode=1,
        )

        seasons = conn.execute(
            "SELECT * FROM seasons WHERE tv_show_id = ?", (tv_id,)
        ).fetchall()
        assert len(seasons) == 2
        season_numbers = {s["season_number"] for s in seasons}
        assert season_numbers == {1, 2}

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        assert len(episodes) == 3

        ep_links = conn.execute("SELECT * FROM episode_files").fetchall()
        assert len(ep_links) == 3

    def test_fallback_to_s01e01_when_no_season_episode(self) -> None:
        from app.library.coordinator import _link_tv_media_file

        conn = _connection()
        conn.execute("INSERT INTO tv_shows(title) VALUES (?)", ("Test Show",))
        tv_id = conn.execute("SELECT id FROM tv_shows").fetchone()["id"]
        conn.execute(
            "INSERT INTO media_files(path, filename, extension) VALUES (?, ?, ?)",
            ("/tmp/test.mkv", "test.mkv", ".mkv"),
        )
        mf_id = conn.execute("SELECT id FROM media_files").fetchone()["id"]

        _link_tv_media_file(
            connection=conn,
            tv_show_id=tv_id,
            media_file_id=mf_id,
        )

        seasons = conn.execute(
            "SELECT * FROM seasons WHERE tv_show_id = ?", (tv_id,)
        ).fetchall()
        assert len(seasons) == 1
        assert seasons[0]["season_number"] == 1

        episodes = conn.execute(
            "SELECT * FROM episodes WHERE season_id = ?", (seasons[0]["id"],)
        ).fetchall()
        assert len(episodes) == 1
        assert episodes[0]["episode_number"] == 1

    def test_tv_linking_idempotent(self) -> None:
        from app.library.coordinator import _link_tv_media_file

        conn = _connection()
        conn.execute("INSERT INTO tv_shows(title) VALUES (?)", ("Test Show",))
        tv_id = conn.execute("SELECT id FROM tv_shows").fetchone()["id"]
        conn.execute(
            "INSERT INTO media_files(path, filename, extension) VALUES (?, ?, ?)",
            ("/tmp/test.mkv", "test.mkv", ".mkv"),
        )
        mf_id = conn.execute("SELECT id FROM media_files").fetchone()["id"]

        _link_tv_media_file(
            connection=conn,
            tv_show_id=tv_id,
            media_file_id=mf_id,
            season=1,
            episode=1,
        )
        _link_tv_media_file(
            connection=conn,
            tv_show_id=tv_id,
            media_file_id=mf_id,
            season=1,
            episode=1,
        )

        seasons = conn.execute(
            "SELECT * FROM seasons WHERE tv_show_id = ?", (tv_id,)
        ).fetchall()
        assert len(seasons) == 1

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        assert len(episodes) == 1

        ep_links = conn.execute("SELECT * FROM episode_files").fetchall()
        assert len(ep_links) == 1

    def test_identification_produces_correct_season_episode(self) -> None:
        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path("/tmp/Show.S03E07.mkv"),
            filename="Show.S03E07.mkv",
            extension=".mkv",
            size_bytes=1000,
        )
        id_result = identify(scan_result, parent_parts=["TV Shows"])

        assert id_result.media_type == MediaType.EPISODE
        assert id_result.season == 3
        assert id_result.episode == 7

    def test_identification_produces_s01e01(self) -> None:
        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path("/tmp/Breaking.Bad.S01E01.720p.mkv"),
            filename="Breaking.Bad.S01E01.720p.mkv",
            extension=".mkv",
            size_bytes=1000,
        )
        id_result = identify(scan_result, parent_parts=["TV Shows", "Breaking Bad"])

        assert id_result.media_type == MediaType.EPISODE
        assert id_result.season == 1
        assert id_result.episode == 1

    def test_identification_multi_episode(self) -> None:
        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path("/tmp/Show.S01E01E02.mkv"),
            filename="Show.S01E01E02.mkv",
            extension=".mkv",
            size_bytes=1000,
        )
        id_result = identify(scan_result, parent_parts=["TV Shows"])

        assert id_result.media_type == MediaType.EPISODE
        assert id_result.season == 1
        assert id_result.episode == 1
        assert id_result.episode_end == 2

    def test_full_tv_pipeline_with_correct_season_episode(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "TV"
        lib_dir.mkdir()
        (lib_dir / "Show.S02E05.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        mf = conn.execute("SELECT * FROM media_files").fetchone()

        from app.library.scanner import ScanResult as SR
        from app.metadata.identifier import identify

        scan_result = SR(
            path=Path(mf["path"]),
            filename=mf["filename"],
            extension=mf["extension"],
            size_bytes=mf["size_bytes"],
        )
        id_result = identify(scan_result, parent_parts=["TV Shows"])

        assert id_result.season == 2
        assert id_result.episode == 5

        from app.library.coordinator import _link_media_file

        conn.execute("INSERT INTO tv_shows(title) VALUES (?)", ("Show",))
        tv_id = conn.execute("SELECT id FROM tv_shows").fetchone()["id"]

        _link_media_file(
            connection=conn,
            media_file_id=mf["id"],
            entity_type="tv",
            entity_id=tv_id,
            season=id_result.season,
            episode=id_result.episode,
        )

        seasons = conn.execute(
            "SELECT * FROM seasons WHERE tv_show_id = ?", (tv_id,)
        ).fetchall()
        assert len(seasons) == 1
        assert seasons[0]["season_number"] == 2

        episodes = conn.execute(
            "SELECT * FROM episodes WHERE season_id = ?", (seasons[0]["id"],)
        ).fetchall()
        assert len(episodes) == 1
        assert episodes[0]["episode_number"] == 5
