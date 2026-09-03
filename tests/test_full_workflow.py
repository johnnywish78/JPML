from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from app.database.schema import initialize
from app.library.coordinator import process_library_metadata, sync_location
from app.library.favorites_repository import FavoritesRepository
from app.library.media_repository import MediaRepository
from app.library.playback_repository import PlaybackRepository
from app.library.watchlist_repository import WatchlistRepository
from app.metadata.identifier import identify
from app.metadata.library_integration import LibraryMetadataIntegration
from app.metadata.provider import StaticMetadataProvider
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService
from app.player import MockPlayerBackend
from app.services.collections import CollectionsService
from app.services.discovery import DiscoveryService
from app.services.favorites import FavoritesService
from app.services.music import MusicService
from app.library.discovery_repository import DiscoveryRepository
from app.library.collections_repository import CollectionsRepository
from app.library.music_repository import MusicRepository
from app.library.search import SearchRepository
from app.library.statistics_repository import StatisticsRepository
from app.library.watchlist_repository import WatchlistRepository
from app.services.search import SearchService
from app.services.statistics import StatisticsService
from app.services.watchlist import WatchlistService
from app.services.playback import PlaybackService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


def _make_file(path: Path, content: bytes = b"\x00" * 1024) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _movie_integration(conn: sqlite3.Connection) -> LibraryMetadataIntegration:
    provider = StaticMetadataProvider(
        {
            "movie:tt0408279": {
                "title": "Inception",
                "year": 2010,
                "overview": "Dreams inside dreams.",
                "genres": ["Action", "Sci-Fi"],
                "external_id": "tt0408279",
            }
        }
    )
    service = MetadataService(MetadataRepository(conn), provider=provider)
    music_service = MusicService(MusicRepository(conn))
    return LibraryMetadataIntegration(service, music_service=music_service)


class TestMovieEndToEndWorkflow:
    def test_full_movie_pipeline(self) -> None:
        conn = _connection()
        integration = _movie_integration(conn)

        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp)
            movie_file = _make_file(lib / "Movies" / "Inception.2010.mkv")

            # 1. scan + sync
            sync = sync_location(conn, lib)
            assert sync.scan_stats.media_files_found == 1
            assert sync.files_added == 1

            # 2. identification (no external_id -> local entity)
            media = MediaRepository(conn).list_all()
            assert len(media) == 1
            from app.library.scanner import ScanResult

            id_result = identify(
                ScanResult(
                    path=Path(media[0].path),
                    filename=movie_file.name,
                    extension=".mkv",
                    size_bytes=1024,
                ),
                parent_parts=["Movies"],
            )
            lib_result = integration.process_identification(id_result)
            assert lib_result.resolution.entity_type == "movie"
            movie_id = lib_result.resolution.entity_id

            # link file
            conn.execute(
                "INSERT OR IGNORE INTO movie_files(movie_id, media_file_id) "
                "VALUES (?, ?)",
                (movie_id, media[0].id),
            )
            conn.commit()

        # 4. favorites
        favorites = FavoritesService(FavoritesRepository(conn))
        favorites.add("movie", movie_id)
        assert favorites.is_favorite("movie", movie_id) is True

        # 5. watchlist
        watchlist = WatchlistService(WatchlistRepository(conn))
        watchlist.add("movie", movie_id)
        assert watchlist.is_in_watchlist("movie", movie_id) is True

        # 6. collections
        collections = CollectionsService(CollectionsRepository(conn))
        c = collections.create("Sci-Fi")
        collections.add_item(c.id, "movie", movie_id)
        assert collections.contains(c.id, "movie", movie_id) is True

        # 7. search finds everything
        search = SearchService(SearchRepository(conn))
        films = search.search_movies("inception")
        assert films and films[0].entity_id == movie_id
        all_results = search.search_all("inception")
        assert any(r.entity_type == "movie" and r.entity_id == movie_id
                   for r in all_results)

        # 8. playback: open, progress, resume
        repo = PlaybackRepository(conn)
        backend = MockPlayerBackend()
        svc = PlaybackService(backend, repo)
        svc.open("movie", movie_id, "/Movies/Inception.2010.mkv",
                 backend_used="mock")
        svc.play()
        svc.seek(300.0)
        svc.stop()
        assert repo.get_position("movie", movie_id) == 300.0

        # 9. resume candidates + restart restores position
        candidates = repo.get_resume_candidates()
        assert len(candidates) == 1
        assert candidates[0]["last_position"] == 300.0

        svc.open("movie", movie_id, "/Movies/Inception.2010.mkv",
                 backend_used="mock")
        assert backend.get_position() == 300.0

        # 10. completion
        svc.mark_completed()
        svc.stop()
        assert repo.is_completed("movie", movie_id) is True
        assert svc.get_resume_position("movie", movie_id) == 0.0

        # 11. statistics
        stats = StatisticsService(StatisticsRepository(conn))
        library = stats.library()
        assert library.total_movies == 1
        assert library.total_media_files == 1
        playback = stats.playback()
        assert playback.completed == 1
        breakdown = stats.media_breakdown()
        assert breakdown.movies_with_files == 1

        # 12. discovery: item shows as played; trending reflects activity
        discovery = DiscoveryService(DiscoveryRepository(conn))
        trending = discovery.trending(10)
        assert [t.title for t in trending] == ["Inception"]
        recs = discovery.recommendations("movie", movie_id, 5)
        assert all(r.entity_id != movie_id for r in recs)

    def test_persistence_across_database_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_file = str(Path(tmp) / "persist.db")

            conn = sqlite3.connect(db_file)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            initialize(conn)
            conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Persist')")
            conn.commit()
            FavoritesService(FavoritesRepository(conn)).add("movie", 1)
            repo = PlaybackRepository(conn)
            repo.start_playback("movie", 1, "/p.mkv")
            repo.update_position("movie", 1, 42.0)
            conn.close()

            conn = sqlite3.connect(db_file)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            initialize(conn)
            assert (
                FavoritesService(FavoritesRepository(conn)).is_favorite(
                    "movie", 1
                )
                is True
            )
            assert PlaybackRepository(conn).get_position("movie", 1) == 42.0
            conn.close()


class TestMusicEndToEndWorkflow:
    def test_music_pipeline(self) -> None:
        conn = _connection()
        integration = _movie_integration(conn)

        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp)
            _make_file(
                lib / "Music" / "Daft Punk" / "Random Access Memories"
                / "08 - Get Lucky.mp3"
            )
            _make_file(
                lib / "Music" / "Daft Punk" / "Random Access Memories"
                / "01 - Give Life Back To Music.mp3"
            )

            # 1. sync
            sync = sync_location(conn, lib)
            assert sync.scan_stats.media_files_found == 2
            assert sync.files_added == 2

            # 2. metadata processing resolves artist/album/track + links
            proc = process_library_metadata(conn, integration=integration)
            assert proc.files_processed == 2
            assert proc.files_skipped == 0
            assert proc.errors == []

            # 3. idempotent reprocessing
            proc2 = process_library_metadata(conn, integration=integration)
            assert proc2.files_processed == 0
            assert proc2.files_skipped == 2

        music = MusicService(MusicRepository(conn))
        tracks = music.search_tracks("lucky")
        assert len(tracks) == 1
        assert tracks[0].artist.name == "Daft Punk"
        assert tracks[0].album.title == "Random Access Memories"
        assert tracks[0].track_number == 8

        albums = music.search_albums("random access")
        assert len(albums) == 1
        artists = music.search_artists("daft punk")
        assert len(artists) == 1
        assert artists[0].id is not None

        # 4. search service sees music
        search = SearchService(SearchRepository(conn))
        all_results = search.search_all("get lucky")
        assert any(r.entity_type == "track" for r in all_results)
        music_results = search.search_music("daft")
        assert any(r.entity_type == "artist" for r in music_results)

        # 5. favorites / watchlist / collections for music entities
        favorites = FavoritesService(FavoritesRepository(conn))
        favorites.add("artist", artists[0].id)
        assert favorites.is_favorite("artist", artists[0].id) is True

        watchlist = WatchlistService(WatchlistRepository(conn))
        watchlist.add("album", albums[0].id)
        assert watchlist.is_in_watchlist("album", albums[0].id) is True

        collections = CollectionsService(CollectionsRepository(conn))
        c = collections.create("Electronic")
        collections.add_item(c.id, "track", tracks[0].id)
        assert collections.contains(c.id, "track", tracks[0].id) is True

        # 6. statistics include music
        stats = StatisticsService(StatisticsRepository(conn))
        library = stats.library()
        assert library.total_artists == 1
        assert library.total_albums == 1
        assert library.total_tracks == 2
        assert library.total_media_files == 2
        breakdown = stats.media_breakdown()
        assert breakdown.tracks_with_files == 2

        # 7. playback for a music track
        backend = MockPlayerBackend()
        repo = PlaybackRepository(conn)
        svc = PlaybackService(backend, repo)
        svc.open("track", tracks[0].id, "/Music/get_lucky.mp3",
                 backend_used="mock")
        svc.play()
        svc.seek(30.0)
        svc.stop()
        assert repo.get_position("track", tracks[0].id) == 30.0

        # 8. missing-file detection
        media_repo = MediaRepository(conn)
        first = media_repo.list_all()[0]
        media_repo.mark_missing(first.id)
        assert len(media_repo.get_missing()) == 1
        assert stats.library().missing_media_files == 1

    def test_music_files_missing_then_recovered(self) -> None:
        conn = _connection()
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp)
            f = _make_file(lib / "Artists" / "A" / "Album" / "01 Song.mp3")

            sync_location(conn, lib)
            os.unlink(f)
            sync_again = sync_location(conn, lib)
            assert sync_again.files_missing == 1

            media_repo = MediaRepository(conn)
            assert len(media_repo.get_missing()) == 1

            # file returns
            _make_file(lib / "Artists" / "A" / "Album" / "01 Song.mp3")
            sync_location(conn, lib)
            assert len(media_repo.get_missing()) == 0
