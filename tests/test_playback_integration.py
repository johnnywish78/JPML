from __future__ import annotations

import sqlite3

import pytest

from app.library.playback_repository import PlaybackRepository
from app.player import MockPlayerBackend
from app.services.playback import PlaybackService


def _make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS playback_history (
            id INTEGER PRIMARY KEY,
            media_type TEXT NOT NULL,
            media_id INTEGER NOT NULL,
            file_path TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            stopped_at TEXT,
            last_position REAL DEFAULT 0.0,
            duration REAL DEFAULT 0.0,
            completed INTEGER DEFAULT 0,
            backend_used TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_playback_history_media
            ON playback_history(media_type, media_id);
        CREATE INDEX IF NOT EXISTS idx_playback_history_started
            ON playback_history(started_at);

        CREATE TABLE IF NOT EXISTS library_files (
            id INTEGER PRIMARY KEY,
            file_path TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL DEFAULT '',
            file_size INTEGER DEFAULT 0,
            file_modified_time REAL DEFAULT 0.0,
            media_type TEXT NOT NULL DEFAULT '',
            detected_type TEXT DEFAULT '',
            library_location TEXT DEFAULT '',
            scan_date TEXT NOT NULL,
            last_modified_scan TEXT NOT NULL,
            detected_title TEXT DEFAULT '',
            detected_year INTEGER,
            detected_season INTEGER,
            detected_episode INTEGER,
            file_status TEXT NOT NULL DEFAULT 'present'
        );

        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            year INTEGER
        );

        INSERT INTO schema_version(version) VALUES (6);
        """
    )
    return connection


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = _make_connection()
    yield conn
    conn.close()


@pytest.fixture()
def repo(db: sqlite3.Connection) -> PlaybackRepository:
    return PlaybackRepository(db)


@pytest.fixture()
def backend() -> MockPlayerBackend:
    return MockPlayerBackend()


@pytest.fixture()
def svc(backend: MockPlayerBackend, repo: PlaybackRepository) -> PlaybackService:
    return PlaybackService(backend, repo)


# ── A. Starting playback creates/updates playback_history ─────────────────────

class TestStartCreatesRecord:
    def test_open_creates_history_record(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/inception.mkv", backend_used="mock")
        row = repo._conn.execute(
            "SELECT * FROM playback_history WHERE media_type = 'movie' AND media_id = 1"
        ).fetchone()
        assert row is not None
        assert row["file_path"] == "/movies/inception.mkv"
        assert row["backend_used"] == "mock"
        assert row["completed"] == 0
        assert row["last_position"] == 0.0

    def test_open_on_replay_resets_record(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.open("movie", 1, "/movies/a.mkv")
        count = repo._conn.execute(
            "SELECT COUNT(*) FROM playback_history WHERE media_type = 'movie' AND media_id = 1"
        ).fetchone()[0]
        assert count == 1

    def test_open_records_backend_used(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv", backend_used="mpv")
        row = repo._conn.execute(
            "SELECT backend_used FROM playback_history WHERE media_id = 1"
        ).fetchone()
        assert row["backend_used"] == "mpv"


# ── B. Position is persisted ──────────────────────────────────────────────────

class TestPositionPersisted:
    def test_pause_persists_position(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(120.0)
        svc.pause()
        assert repo.get_position("movie", 1) == 120.0

    def test_stop_persists_position(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(300.0)
        svc.stop()
        assert repo.get_position("movie", 1) == 300.0

    def test_close_persists_position(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(450.0)
        svc.close()
        assert repo.get_position("movie", 1) == 450.0

    def test_save_position_persists(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(600.0)
        svc.save_position()
        assert repo.get_position("movie", 1) == 600.0

    def test_seek_persists_position(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.seek(90.0)
        assert repo.get_position("movie", 1) == 90.0


# ── C. Reopening retrieves previous position ──────────────────────────────────

class TestReopenRetrievesPosition:
    def test_reopen_seeks_to_resume_position(
        self, svc: PlaybackService, backend: MockPlayerBackend
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(200.0)
        svc.stop()

        svc.open("movie", 1, "/movies/a.mkv")
        assert backend.get_position() == 200.0

    def test_get_resume_position_returns_saved(
        self, svc: PlaybackService
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(500.0)
        svc.stop()

        assert svc.get_resume_position("movie", 1) == 500.0

    def test_open_returns_resume_position(
        self, svc: PlaybackService
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(150.0)
        svc.stop()

        result = svc.open("movie", 1, "/movies/a.mkv")
        assert result == 150.0


# ── D. Completion marks item completed ────────────────────────────────────────

class TestCompletion:
    def test_mark_completed_persists(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(7200.0)
        svc.mark_completed()
        assert repo.is_completed("movie", 1) is True

    def test_mark_completed_via_service(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.mark_completed()
        assert svc.is_completed("movie", 1) is True
        assert repo.is_completed("movie", 1) is True


# ── E. Completed item resumes from zero ───────────────────────────────────────

class TestCompletedResumesFromZero:
    def test_completed_item_returns_zero_resume(
        self, svc: PlaybackService
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(5000.0)
        svc.mark_completed()
        svc.stop()

        assert svc.get_resume_position("movie", 1) == 0.0

    def test_reopen_after_completion_starts_from_zero(
        self, svc: PlaybackService, backend: MockPlayerBackend
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(5000.0)
        svc.mark_completed()
        svc.stop()

        svc.open("movie", 1, "/movies/a.mkv")
        assert backend.get_position() == 0.0


# ── F. Stopping preserves position ────────────────────────────────────────────

class TestStopPreservesPosition:
    def test_stop_then_reopen_restores(
        self, svc: PlaybackService, backend: MockPlayerBackend
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(999.0)
        svc.stop()

        svc.open("movie", 1, "/movies/a.mkv")
        assert backend.get_position() == 999.0

    def test_stop_does_not_mark_completed(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(100.0)
        svc.stop()
        assert repo.is_completed("movie", 1) is False


# ── G. Repeated playback does not create duplicate records ────────────────────

class TestNoDuplicateRecords:
    def test_single_record_per_media_type_id(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        for _ in range(5):
            svc.open("movie", 1, "/movies/a.mkv")
            svc.play()
            svc.seek(100.0)
            svc.stop()

        count = repo._conn.execute(
            "SELECT COUNT(*) FROM playback_history WHERE media_type = 'movie' AND media_id = 1"
        ).fetchone()[0]
        assert count == 1

    def test_different_media_types_are_independent(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(100.0)
        svc.stop()

        svc.open("episode", 1, "/shows/s01e01.mkv")
        svc.play()
        svc.seek(200.0)
        svc.stop()

        assert repo.get_position("movie", 1) == 100.0
        assert repo.get_position("episode", 1) == 200.0
        count = repo._conn.execute("SELECT COUNT(*) FROM playback_history").fetchone()[0]
        assert count == 2


# ── H. Player failure does not corrupt library metadata ───────────────────────

class TestPlayerFailureSafety:
    def test_close_after_open_is_safe(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.close()
        assert repo.get_position("movie", 1) == 0.0

    def test_stop_without_open_is_safe(
        self, svc: PlaybackService
    ) -> None:
        svc.stop()

    def test_pause_without_play_is_safe(
        self, svc: PlaybackService
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.pause()

    def test_close_preserves_position_but_resets_state(
        self, svc: PlaybackService, backend: MockPlayerBackend
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(500.0)
        svc.close()
        assert backend.is_open() is False

        svc.open("movie", 1, "/movies/a.mkv")
        assert backend.get_position() == 500.0

    def test_multiple_media_ids_isolated(
        self, svc: PlaybackService, repo: PlaybackRepository
    ) -> None:
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(100.0)
        svc.stop()

        svc.open("movie", 2, "/movies/b.mkv")
        svc.play()
        svc.seek(200.0)
        svc.stop()

        assert repo.get_position("movie", 1) == 100.0
        assert repo.get_position("movie", 2) == 200.0

    def test_library_tables_unaffected_by_playback(
        self, svc: PlaybackService, db: sqlite3.Connection
    ) -> None:
        db.execute(
            "INSERT INTO movies(id, title) VALUES (1, 'Test')"
        )
        db.commit()
        svc.open("movie", 1, "/movies/a.mkv")
        svc.play()
        svc.seek(100.0)
        svc.stop()
        svc.close()
        row = db.execute("SELECT title FROM movies WHERE id = 1").fetchone()
        assert row["title"] == "Test"
