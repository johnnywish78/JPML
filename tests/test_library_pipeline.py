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


class TestPhase5CoordinatorMoviePipeline:
    def test_full_movie_pipeline_through_coordinator(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")
        (lib_dir / "The Matrix (1999).mkv").write_bytes(b"")

        conn = _connection()
        sync_result = sync_location(conn, lib_dir)
        assert sync_result.files_added == 2

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        proc_result = process_library_metadata(conn, integration=integration)

        assert proc_result.files_processed == 2
        assert proc_result.entities_created == 2
        assert proc_result.errors == []

        movies = conn.execute("SELECT * FROM movies").fetchall()
        assert len(movies) == 2

        movie_files = conn.execute("SELECT * FROM movie_files").fetchall()
        assert len(movie_files) == 2

    def test_movie_with_external_id_full_coordinator_flow(
        self, tmp_path: Path
    ) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "genres": ["Sci-Fi"],
                "external_id": "tt1375666",
            },
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
        from app.library.coordinator import _link_media_file
        _link_media_file(
            connection=conn,
            media_file_id=mf["id"],
            entity_type=lib_result.resolution.entity_type,
            entity_id=lib_result.resolution.entity_id,
        )

        movie_id = lib_result.resolution.entity_id
        eids = repo.list_external_ids("movie", movie_id)
        assert len(eids) == 1
        assert eids[0]["external_id"] == "tt1375666"

        genres = repo.get_movie_genres(movie_id)
        assert "Sci-Fi" in genres

        source = repo.get_metadata_source("movie", movie_id, "static")
        assert source is not None


class TestPhase5CoordinatorTVPipeline:
    def test_full_tv_pipeline_s01e01(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "TV"
        lib_dir.mkdir()
        (lib_dir / "Breaking.Bad.S01E01.720p.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        proc_result = process_library_metadata(
            conn, integration=integration, parent_parts=["TV Shows"]
        )

        assert proc_result.files_processed == 1
        assert proc_result.entities_created == 1
        assert proc_result.errors == []

        tv_shows = conn.execute("SELECT * FROM tv_shows").fetchall()
        assert len(tv_shows) == 1

        seasons = conn.execute("SELECT * FROM seasons").fetchall()
        assert len(seasons) == 1
        assert seasons[0]["season_number"] == 1

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        assert len(episodes) == 1
        assert episodes[0]["episode_number"] == 1

        ep_files = conn.execute("SELECT * FROM episode_files").fetchall()
        assert len(ep_files) == 1

    def test_full_tv_pipeline_s02e05(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "TV"
        lib_dir.mkdir()
        (lib_dir / "Breaking.Bad.S02E05.720p.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        proc_result = process_library_metadata(
            conn, integration=integration, parent_parts=["TV Shows"]
        )

        assert proc_result.files_processed == 1
        assert proc_result.errors == []

        seasons = conn.execute("SELECT * FROM seasons").fetchall()
        assert len(seasons) == 1
        assert seasons[0]["season_number"] == 2

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        assert len(episodes) == 1
        assert episodes[0]["episode_number"] == 5

    def test_tv_with_external_id_full_flow(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "TV"
        lib_dir.mkdir()
        (lib_dir / "Show.S01E01.mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "tv:tt1234567": {
                "title": "Test Show",
                "year": 2020,
                "genres": ["Drama", "Thriller"],
                "external_id": "tt1234567",
            },
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
        id_result = identify(scan_result, parent_parts=["TV Shows"])
        id_result.provider = "static"
        id_result.external_id = "tt1234567"

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
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

        tv_id = lib_result.resolution.entity_id
        genres = repo.get_tv_genres(tv_id)
        assert "Drama" in genres
        assert "Thriller" in genres

        source = repo.get_metadata_source("tv", tv_id, "static")
        assert source is not None


class TestPhase5CoordinatorIdempotency:
    def test_process_library_metadata_idempotent(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")
        (lib_dir / "Test Movie.mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "genres": ["Sci-Fi"],
                "external_id": "tt1375666",
            },
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        sync_location(conn, lib_dir)

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        result1 = process_library_metadata(conn, integration=integration)
        result2 = process_library_metadata(conn, integration=integration)

        assert result1.files_processed == 2
        assert result2.files_processed == 2
        assert result1.entities_created == 2
        assert result2.entities_reused == 2

        movies = conn.execute("SELECT * FROM movies").fetchall()
        assert len(movies) == 2

        movie_files = conn.execute("SELECT * FROM movie_files").fetchall()
        assert len(movie_files) == 2

    def test_process_tv_metadata_idempotent(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "TV"
        lib_dir.mkdir()
        (lib_dir / "Show.S01E01.mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "tv:tt1234567": {
                "title": "Test Show",
                "year": 2020,
                "genres": ["Drama"],
                "external_id": "tt1234567",
            },
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        sync_location(conn, lib_dir)

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        result1 = process_library_metadata(
            conn, integration=integration, parent_parts=["TV Shows"]
        )
        result2 = process_library_metadata(
            conn, integration=integration, parent_parts=["TV Shows"]
        )

        assert result1.files_processed == 1
        assert result2.files_processed == 1
        assert result2.entities_reused == 1

        seasons = conn.execute("SELECT * FROM seasons").fetchall()
        assert len(seasons) == 1

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        assert len(episodes) == 1

        ep_files = conn.execute("SELECT * FROM episode_files").fetchall()
        assert len(ep_files) == 1


class TestPhase5CoordinatorPartialFailure:
    def test_one_identification_failure_does_not_stop_others(
        self, tmp_path: Path
    ) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Good Movie.mkv").write_bytes(b"")
        (lib_dir / "Another Good Movie.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        repo = MetadataRepository(conn)
        service = MetadataService(repo)
        integration = LibraryMetadataIntegration(service)

        import app.metadata.identifier as ident_mod
        original_identify = ident_mod.identify

        call_count = 0

        def patched_identify(scan_result, parent_parts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated identification failure")
            return original_identify(scan_result, parent_parts=parent_parts)

        ident_mod.identify = patched_identify
        try:
            proc_result = process_library_metadata(
                conn, integration=integration, parent_parts=["Movies"]
            )

            assert proc_result.files_processed == 1
            assert len(proc_result.errors) == 1

            movies = conn.execute("SELECT * FROM movies").fetchall()
            assert len(movies) == 1
        finally:
            ident_mod.identify = original_identify

    def test_provider_failure_does_not_stop_other_files(
        self, tmp_path: Path
    ) -> None:
        class FailingProvider(MetadataProvider):
            name = "failing"

            def fetch_metadata(self, *, entity_type: str, external_id: str):
                raise ConnectionError("network down")

        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Failing Movie.mkv").write_bytes(b"")
        (lib_dir / "Good Movie.mkv").write_bytes(b"")

        conn = _connection()
        sync_location(conn, lib_dir)

        repo = MetadataRepository(conn)
        service = MetadataService(repo, provider=FailingProvider())
        integration = LibraryMetadataIntegration(service)

        proc_result = process_library_metadata(
            conn, integration=integration, parent_parts=["Movies"]
        )

        assert proc_result.files_processed == 2
        assert proc_result.errors == []

        movies = conn.execute("SELECT * FROM movies").fetchall()
        assert len(movies) == 2


class TestPhase5MetadataSource:
    def test_metadata_source_recorded_with_external_id(
        self, tmp_path: Path
    ) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "genres": ["Sci-Fi"],
                "external_id": "tt1375666",
            },
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
        from app.library.coordinator import _link_media_file
        _link_media_file(
            connection=conn,
            media_file_id=mf["id"],
            entity_type=lib_result.resolution.entity_type,
            entity_id=lib_result.resolution.entity_id,
        )

        movie_id = lib_result.resolution.entity_id
        source = repo.get_metadata_source("movie", movie_id, "static")
        assert source is not None
        assert source["provider"] == "static"

    def test_metadata_source_upserted_not_duplicated(
        self, tmp_path: Path
    ) -> None:
        lib_dir = tmp_path / "Movies"
        lib_dir.mkdir()
        (lib_dir / "Inception (2010).mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "genres": ["Sci-Fi"],
                "external_id": "tt1375666",
            },
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

        integration.process_identification(id_result)
        integration.process_identification(id_result)

        movies = conn.execute("SELECT * FROM movies").fetchall()
        movie_id = movies[0]["id"]

        sources = conn.execute(
            "SELECT * FROM metadata_sources WHERE entity_type = 'movie' AND entity_id = ?",
            (movie_id,),
        ).fetchall()
        assert len(sources) == 1

    def test_tv_metadata_source_recorded(self, tmp_path: Path) -> None:
        lib_dir = tmp_path / "TV"
        lib_dir.mkdir()
        (lib_dir / "Show.S01E01.mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "tv:tt1234567": {
                "title": "Test Show",
                "year": 2020,
                "genres": ["Drama"],
                "external_id": "tt1234567",
            },
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
        id_result = identify(scan_result, parent_parts=["TV Shows"])
        id_result.provider = "static"
        id_result.external_id = "tt1234567"

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
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

        tv_id = lib_result.resolution.entity_id
        source = repo.get_metadata_source("tv", tv_id, "static")
        assert source is not None
        assert source["provider"] == "static"


class TestPhase5MixedLibrary:
    def test_mixed_movie_and_tv_files(self, tmp_path: Path) -> None:
        movie_dir = tmp_path / "Movies"
        movie_dir.mkdir()
        (movie_dir / "Inception (2010).mkv").write_bytes(b"")

        tv_dir = tmp_path / "TV"
        tv_dir.mkdir()
        (tv_dir / "Breaking.Bad.S01E01.720p.mkv").write_bytes(b"")

        provider = StaticMetadataProvider({
            "movie:tt1375666": {
                "title": "Inception",
                "year": 2010,
                "genres": ["Sci-Fi"],
                "external_id": "tt1375666",
            },
            "tv:tt0903747": {
                "title": "Breaking Bad",
                "year": 2008,
                "genres": ["Drama"],
                "external_id": "tt0903747",
            },
        })
        registry = MetadataProviderRegistry()
        registry.register(provider)

        conn = _connection()
        sync_location(conn, movie_dir)
        sync_location(conn, tv_dir)

        assert MediaRepository(conn).count() == 2

        repo = MetadataRepository(conn)
        service = MetadataService(repo, registry=registry)
        integration = LibraryMetadataIntegration(service)

        proc_result = process_library_metadata(conn, integration=integration)

        assert proc_result.files_processed == 2
        assert proc_result.entities_created == 2
        assert proc_result.errors == []

        movies = conn.execute("SELECT * FROM movies").fetchall()
        assert len(movies) == 1

        tv_shows = conn.execute("SELECT * FROM tv_shows").fetchall()
        assert len(tv_shows) == 1

        movie_files = conn.execute("SELECT * FROM movie_files").fetchall()
        assert len(movie_files) == 1

        ep_files = conn.execute("SELECT * FROM episode_files").fetchall()
        assert len(ep_files) == 1
