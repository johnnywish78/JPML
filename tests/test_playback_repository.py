from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.library.playback_repository import PlaybackRepository


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

        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY,
            tv_show_id INTEGER NOT NULL,
            season_number INTEGER NOT NULL DEFAULT 0,
            episode_number INTEGER NOT NULL DEFAULT 0,
            title TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS movie_files (
            id INTEGER PRIMARY KEY,
            movie_id INTEGER NOT NULL,
            library_file_id INTEGER NOT NULL,
            is_primary INTEGER DEFAULT 0,
            date_added TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS episode_files (
            id INTEGER PRIMARY KEY,
            episode_id INTEGER NOT NULL,
            library_file_id INTEGER NOT NULL,
            is_primary INTEGER DEFAULT 0,
            date_added TEXT NOT NULL
        );

        INSERT INTO schema_version(version) VALUES (5);
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insert_library_file(
    db: sqlite3.Connection,
    file_path: str,
    *,
    media_type: str = "movie",
    file_status: str = "present",
) -> int:
    now = _now()
    cursor = db.execute(
        """
        INSERT INTO library_files
            (file_path, file_name, media_type, scan_date,
             last_modified_scan, file_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (file_path, file_path.rsplit("/", 1)[-1], media_type, now, now, file_status),
    )
    db.commit()
    return int(cursor.lastrowid)


def _insert_movie(db: sqlite3.Connection, title: str = "Test Movie") -> int:
    cursor = db.execute("INSERT INTO movies(title) VALUES (?)", (title,))
    db.commit()
    return int(cursor.lastrowid)


def _insert_episode(
    db: sqlite3.Connection, tv_show_id: int = 1, title: str = "Test Episode"
) -> int:
    cursor = db.execute(
        "INSERT INTO episodes(tv_show_id, title) VALUES (?, ?)",
        (tv_show_id, title),
    )
    db.commit()
    return int(cursor.lastrowid)


def _link_movie_file(
    db: sqlite3.Connection, movie_id: int, library_file_id: int
) -> int:
    now = _now()
    cursor = db.execute(
        "INSERT INTO movie_files(movie_id, library_file_id, date_added) VALUES (?, ?, ?)",
        (movie_id, library_file_id, now),
    )
    db.commit()
    return int(cursor.lastrowid)


def _link_episode_file(
    db: sqlite3.Connection, episode_id: int, library_file_id: int
) -> int:
    now = _now()
    cursor = db.execute(
        "INSERT INTO episode_files(episode_id, library_file_id, date_added) VALUES (?, ?, ?)",
        (episode_id, library_file_id, now),
    )
    db.commit()
    return int(cursor.lastrowid)


# ── Playback history schema basics ────────────────────────────────────────────

class TestPlaybackHistorySchema:
    def test_table_exists(self, db: sqlite3.Connection) -> None:
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='playback_history'"
        ).fetchone()
        assert row is not None

    def test_indexes_exist(self, db: sqlite3.Connection) -> None:
        indexes = {
            row["name"]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='playback_history'"
            )
        }
        assert "idx_playback_history_media" in indexes
        assert "idx_playback_history_started" in indexes

    def test_insert_raw_record(self, db: sqlite3.Connection) -> None:
        now = _now()
        db.execute(
            """
            INSERT INTO playback_history
                (media_type, media_id, file_path, started_at,
                 last_position, duration, completed, backend_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("movie", 1, "/movies/test.mkv", now, 120.0, 7200.0, 0, "mpv"),
        )
        row = db.execute("SELECT * FROM playback_history WHERE media_id = 1").fetchone()
        assert row is not None
        assert row["media_type"] == "movie"
        assert row["last_position"] == 120.0
        assert row["completed"] == 0


# ── start_playback ─────────────────────────────────────────────────────────────

class TestStartPlayback:
    def test_creates_new_record(self, repo: PlaybackRepository) -> None:
        record_id = repo.start_playback(
            "movie", 1, "/movies/test.mkv", duration=7200.0, backend_used="mpv"
        )
        assert record_id > 0
        assert repo.get_position("movie", 1) == 0.0

    def test_idempotent_restart_resets_state(
        self, repo: PlaybackRepository
    ) -> None:
        id1 = repo.start_playback("movie", 1, "/movies/test.mkv")
        repo.update_position("movie", 1, 500.0)
        id2 = repo.start_playback("movie", 1, "/movies/test.mkv")
        assert id1 == id2
        assert repo.get_position("movie", 1) == 0.0
        assert repo.is_completed("movie", 1) is False


# ── update_position ────────────────────────────────────────────────────────────

class TestUpdatePosition:
    def test_new_position(
        self, repo: PlaybackRepository, db: sqlite3.Connection
    ) -> None:
        _insert_movie(db, "Inception")
        repo.update_position("movie", 1, 120.5)
        assert repo.get_position("movie", 1) == 120.5

    def test_overwrite_position(self, repo: PlaybackRepository) -> None:
        repo.update_position("movie", 1, 100.0)
        repo.update_position("movie", 1, 200.0)
        assert repo.get_position("movie", 1) == 200.0

    def test_idempotent_update_on_existing_record(
        self, repo: PlaybackRepository
    ) -> None:
        repo.start_playback("movie", 1, "/movies/a.mkv")
        repo.update_position("movie", 1, 50.0)
        repo.update_position("movie", 1, 75.0)
        count = repo._conn.execute(
            "SELECT COUNT(*) FROM playback_history WHERE media_type = 'movie' AND media_id = 1"
        ).fetchone()[0]
        assert count == 1
        assert repo.get_position("movie", 1) == 75.0

    def test_multiple_media_types_independent(
        self, repo: PlaybackRepository
    ) -> None:
        repo.update_position("movie", 1, 100.0)
        repo.update_position("episode", 1, 200.0)
        repo.update_position("music", 1, 300.0)
        assert repo.get_position("movie", 1) == 100.0
        assert repo.get_position("episode", 1) == 200.0
        assert repo.get_position("music", 1) == 300.0


# ── get_position ───────────────────────────────────────────────────────────────

class TestGetPosition:
    def test_missing_returns_zero(self, repo: PlaybackRepository) -> None:
        assert repo.get_position("movie", 999) == 0.0


# ── mark_completed ─────────────────────────────────────────────────────────────

class TestMarkCompleted:
    def test_mark_completed(self, repo: PlaybackRepository) -> None:
        repo.update_position("movie", 1, 50.0)
        repo.mark_completed("movie", 1)
        assert repo.is_completed("movie", 1) is True

    def test_completion_resets_last_position(
        self, repo: PlaybackRepository
    ) -> None:
        repo.update_position("movie", 1, 50.0)
        repo.mark_completed("movie", 1)
        assert repo.get_last_position("movie", 1) == 0.0

    def test_completed_item_get_position_still_returns_value(
        self, repo: PlaybackRepository
    ) -> None:
        repo.update_position("movie", 1, 50.0)
        repo.mark_completed("movie", 1)
        assert repo.get_position("movie", 1) == 50.0

    def test_mark_completed_on_unknown_creates_record(
        self, repo: PlaybackRepository
    ) -> None:
        repo.mark_completed("movie", 42)
        assert repo.is_completed("movie", 42) is True
        assert repo.get_last_position("movie", 42) == 0.0


# ── is_completed ───────────────────────────────────────────────────────────────

class TestIsCompleted:
    def test_not_completed(self, repo: PlaybackRepository) -> None:
        assert repo.is_completed("movie", 1) is False

    def test_not_completed_after_position_update(
        self, repo: PlaybackRepository
    ) -> None:
        repo.update_position("movie", 1, 100.0)
        assert repo.is_completed("movie", 1) is False

    def test_completed_is_true(self, repo: PlaybackRepository) -> None:
        repo.mark_completed("movie", 1)
        assert repo.is_completed("movie", 1) is True


# ── get_last_position ──────────────────────────────────────────────────────────

class TestGetLastPosition:
    def test_no_state(self, repo: PlaybackRepository) -> None:
        assert repo.get_last_position("movie", 999) == 0.0

    def test_with_position(self, repo: PlaybackRepository) -> None:
        repo.update_position("movie", 1, 150.0)
        assert repo.get_last_position("movie", 1) == 150.0

    def test_completed_returns_zero(self, repo: PlaybackRepository) -> None:
        repo.update_position("movie", 1, 150.0)
        repo.mark_completed("movie", 1)
        assert repo.get_last_position("movie", 1) == 0.0


# ── get_resume_candidates ──────────────────────────────────────────────────────

class TestGetResumeCandidates:
    def test_no_candidates(self, repo: PlaybackRepository) -> None:
        assert repo.get_resume_candidates() == []

    def test_returns_incomplete_with_position(
        self, repo: PlaybackRepository, db: sqlite3.Connection
    ) -> None:
        lf_id = _insert_library_file(db, "/movies/inception.mkv")
        movie_id = _insert_movie(db, "Inception")
        _link_movie_file(db, movie_id, lf_id)

        repo.start_playback("movie", movie_id, "/movies/inception.mkv")
        repo.update_position("movie", movie_id, 100.0)

        candidates = repo.get_resume_candidates()
        assert len(candidates) == 1
        assert candidates[0]["media_type"] == "movie"
        assert candidates[0]["media_id"] == movie_id
        assert candidates[0]["last_position"] == 100.0
        assert candidates[0]["file_path"] == "/movies/inception.mkv"

    def test_excludes_completed(self, repo: PlaybackRepository) -> None:
        repo.start_playback("movie", 1, "/movies/a.mkv")
        repo.update_position("movie", 1, 100.0)
        repo.mark_completed("movie", 1)

        repo.start_playback("movie", 2, "/movies/b.mkv")
        repo.update_position("movie", 2, 200.0)

        candidates = repo.get_resume_candidates()
        assert len(candidates) == 1
        assert candidates[0]["media_id"] == 2

    def test_excludes_zero_position(
        self, repo: PlaybackRepository, db: sqlite3.Connection
    ) -> None:
        lf_id = _insert_library_file(db, "/movies/c.mkv")
        movie_id = _insert_movie(db, "Movie C")
        _link_movie_file(db, movie_id, lf_id)

        repo.start_playback("movie", movie_id, "/movies/c.mkv")
        candidates = repo.get_resume_candidates()
        assert len(candidates) == 0

    def test_excludes_missing_files(
        self, repo: PlaybackRepository, db: sqlite3.Connection
    ) -> None:
        lf_id = _insert_library_file(
            db, "/movies/missing.mkv", file_status="missing"
        )
        movie_id = _insert_movie(db, "Missing Movie")
        _link_movie_file(db, movie_id, lf_id)

        repo.start_playback("movie", movie_id, "/movies/missing.mkv")
        repo.update_position("movie", movie_id, 50.0)

        candidates = repo.get_resume_candidates()
        assert len(candidates) == 0

    def test_includes_present_files(
        self, repo: PlaybackRepository, db: sqlite3.Connection
    ) -> None:
        lf_id = _insert_library_file(db, "/movies/present.mkv", file_status="present")
        movie_id = _insert_movie(db, "Present Movie")
        _link_movie_file(db, movie_id, lf_id)

        repo.start_playback("movie", movie_id, "/movies/present.mkv")
        repo.update_position("movie", movie_id, 50.0)

        candidates = repo.get_resume_candidates()
        assert len(candidates) == 1

    def test_limit(self, repo: PlaybackRepository) -> None:
        for i in range(10):
            repo.start_playback("movie", i + 1, f"/movies/m{i}.mkv")
            repo.update_position("movie", i + 1, 10.0 * (i + 1))

        candidates = repo.get_resume_candidates(limit=3)
        assert len(candidates) == 3

    def test_ordering_by_most_recently_stopped(
        self, repo: PlaybackRepository
    ) -> None:
        repo.start_playback("movie", 1, "/movies/a.mkv")
        repo.update_position("movie", 1, 100.0)

        repo.start_playback("movie", 2, "/movies/b.mkv")
        repo.update_position("movie", 2, 200.0)

        candidates = repo.get_resume_candidates()
        assert candidates[0]["media_id"] == 2
        assert candidates[1]["media_id"] == 1


# ── clear ──────────────────────────────────────────────────────────────────────

class TestClear:
    def test_clear_single(self, repo: PlaybackRepository) -> None:
        repo.update_position("movie", 1, 100.0)
        repo.clear("movie", 1)
        assert repo.get_position("movie", 1) == 0.0

    def test_clear_does_not_affect_other_media(
        self, repo: PlaybackRepository
    ) -> None:
        repo.update_position("movie", 1, 100.0)
        repo.update_position("movie", 2, 200.0)
        repo.clear("movie", 1)
        assert repo.get_position("movie", 1) == 0.0
        assert repo.get_position("movie", 2) == 200.0

    def test_clear_all(self, repo: PlaybackRepository) -> None:
        repo.update_position("movie", 1, 100.0)
        repo.update_position("episode", 1, 200.0)
        repo.clear_all()
        assert repo.get_position("movie", 1) == 0.0
        assert repo.get_position("episode", 1) == 0.0

    def test_clear_all_leaves_other_tables_intact(
        self, repo: PlaybackRepository, db: sqlite3.Connection
    ) -> None:
        _insert_movie(db, "Test")
        repo.update_position("movie", 1, 100.0)
        repo.clear_all()
        assert db.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 1


# ── file_path semantics ───────────────────────────────────────────────────────

class TestFilePathSemantics:
    def test_start_playback_records_file_path(
        self, repo: PlaybackRepository
    ) -> None:
        repo.start_playback("movie", 1, "/movies/inception.mkv")
        row = repo._conn.execute(
            "SELECT file_path FROM playback_history WHERE media_id = 1"
        ).fetchone()
        assert row["file_path"] == "/movies/inception.mkv"

    def test_update_position_records_empty_path_when_no_start(
        self, repo: PlaybackRepository
    ) -> None:
        repo.update_position("movie", 1, 50.0)
        row = repo._conn.execute(
            "SELECT file_path FROM playback_history WHERE media_id = 1"
        ).fetchone()
        assert row["file_path"] == ""

    def test_start_playback_records_backend(
        self, repo: PlaybackRepository
    ) -> None:
        repo.start_playback(
            "movie", 1, "/movies/a.mkv", backend_used="mpv"
        )
        row = repo._conn.execute(
            "SELECT backend_used FROM playback_history WHERE media_id = 1"
        ).fetchone()
        assert row["backend_used"] == "mpv"
