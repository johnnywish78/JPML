from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.database.schema import initialize
from app.domain.media import MediaFile
from app.library.library_repository import LibraryRepository
from app.library.media_repository import MediaRepository
from app.library.coordinator import sync_location


def _make_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


# ─── 8. Library locations CRUD ───────────────────────────────────────────────

def test_add_list_remove_library_locations(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = LibraryRepository(conn)

    loc1 = tmp_path / "Movies"
    loc2 = tmp_path / "TV Shows"
    loc1.mkdir()
    loc2.mkdir()

    id1 = repo.add_location(loc1, label="Movies")
    id2 = repo.add_location(loc2, label="TV Shows")

    locations = repo.list_locations()
    assert len(locations) == 2
    assert locations[0]["label"] == "Movies"
    assert locations[1]["label"] == "TV Shows"

    removed = repo.remove_location(id1)
    assert removed is True

    locations = repo.list_locations()
    assert len(locations) == 1
    assert locations[0]["id"] == id2

    assert repo.remove_location(999) is False


def test_get_location_path(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = LibraryRepository(conn)

    loc = tmp_path / "Media"
    loc.mkdir()
    loc_id = repo.add_location(loc)

    retrieved = repo.get_location_path(loc_id)
    assert retrieved == loc.resolve()

    assert repo.get_location_path(999) is None


# ─── 9. Insert media file ────────────────────────────────────────────────────

def test_insert_media_file(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = MediaRepository(conn)

    mf = MediaFile(
        path=str(tmp_path / "movie.mkv"),
        filename="movie.mkv",
        extension=".mkv",
        size_bytes=1024,
    )

    file_id = repo.upsert(mf)
    assert file_id is not None
    assert file_id > 0


# ─── 10. Retrieve media file by path ─────────────────────────────────────────

def test_retrieve_media_file_by_path(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = MediaRepository(conn)

    path = tmp_path / "movie.mkv"
    path.write_bytes(b"")
    mf = MediaFile(
        path=str(path),
        filename="movie.mkv",
        extension=".mkv",
        size_bytes=path.stat().st_size,
    )

    repo.upsert(mf)
    retrieved = repo.get_by_path(path)

    assert retrieved is not None
    assert retrieved.filename == "movie.mkv"
    assert retrieved.extension == ".mkv"

    assert repo.get_by_path(tmp_path / "nonexistent.mkv") is None


# ─── 11. Duplicate scan does not duplicate records ──────────────────────────

def test_duplicate_scan_no_duplicates(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = MediaRepository(conn)

    path = tmp_path / "movie.mkv"
    path.write_bytes(b"")
    mf = MediaFile(
        path=str(path),
        filename="movie.mkv",
        extension=".mkv",
        size_bytes=100,
    )

    repo.upsert(mf)
    assert repo.count() == 1

    repo.upsert(mf)
    assert repo.count() == 1

    repo.upsert(mf)
    assert repo.count() == 1


# ─── 12. Same filename at different paths creates two records ────────────────

def test_same_filename_different_paths(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = MediaRepository(conn)

    dir_a = tmp_path / "A"
    dir_b = tmp_path / "B"
    dir_a.mkdir()
    dir_b.mkdir()

    (dir_a / "movie.mkv").write_bytes(b"")
    (dir_b / "movie.mkv").write_bytes(b"")

    mf_a = MediaFile(path=str(dir_a / "movie.mkv"), filename="movie.mkv", extension=".mkv")
    mf_b = MediaFile(path=str(dir_b / "movie.mkv"), filename="movie.mkv", extension=".mkv")

    repo.upsert(mf_a)
    repo.upsert(mf_b)

    assert repo.count() == 2


# ─── 13. Missing file detection ──────────────────────────────────────────────

def test_missing_file_detection(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = MediaRepository(conn)

    path = tmp_path / "movie.mkv"
    path.write_bytes(b"")
    mf = MediaFile(path=str(path), filename="movie.mkv", extension=".mkv")
    file_id = repo.upsert(mf)

    assert len(repo.get_missing()) == 0

    repo.mark_missing(file_id)
    missing = repo.get_missing()
    assert len(missing) == 1
    assert missing[0].filename == "movie.mkv"


# ─── 14. File returning after being missing ──────────────────────────────────

def test_file_returning_after_missing(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = MediaRepository(conn)

    path = tmp_path / "movie.mkv"
    path.write_bytes(b"")
    mf = MediaFile(path=str(path), filename="movie.mkv", extension=".mkv")
    file_id = repo.upsert(mf)

    repo.mark_missing(file_id)
    assert len(repo.get_missing()) == 1

    mf_updated = MediaFile(path=str(path), filename="movie.mkv", extension=".mkv", size_bytes=200)
    repo.upsert(mf_updated)
    assert len(repo.get_missing()) == 0

    all_files = repo.list_all()
    assert len(all_files) == 1
    assert all_files[0].size_bytes == 200


# ─── 15. Transaction rollback behavior ───────────────────────────────────────

def test_transaction_rollback(tmp_path: Path) -> None:
    conn = _make_connection()
    repo = MediaRepository(conn)

    mf = MediaFile(path=str(tmp_path / "movie.mkv"), filename="movie.mkv", extension=".mkv")
    repo.upsert(mf)
    assert repo.count() == 1

    try:
        conn.execute("INSERT INTO media_files(path, filename) VALUES (?, ?)", ("dup", "dup"))
        conn.execute("INSERT INTO media_files(path, filename) VALUES (?, ?)", ("dup", "dup"))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()

    assert repo.count() == 1


# ─── Coordinator sync tests ──────────────────────────────────────────────────

def test_sync_scan_adds_files(tmp_path: Path) -> None:
    conn = _make_connection()
    lib_dir = tmp_path / "library"
    lib_dir.mkdir()
    (lib_dir / "movie1.mkv").write_bytes(b"")
    (lib_dir / "movie2.mp4").write_bytes(b"")

    result = sync_location(conn, lib_dir)
    assert result.files_added == 2
    assert MediaRepository(conn).count() == 2


def test_sync_scan_idempotent(tmp_path: Path) -> None:
    conn = _make_connection()
    lib_dir = tmp_path / "library"
    lib_dir.mkdir()
    (lib_dir / "movie.mkv").write_bytes(b"")

    sync_location(conn, lib_dir)
    assert MediaRepository(conn).count() == 1

    sync_location(conn, lib_dir)
    assert MediaRepository(conn).count() == 1


def test_sync_missing_file_marked(tmp_path: Path) -> None:
    conn = _make_connection()
    lib_dir = tmp_path / "library"
    lib_dir.mkdir()
    (lib_dir / "movie1.mkv").write_bytes(b"")
    (lib_dir / "movie2.mkv").write_bytes(b"")

    sync_location(conn, lib_dir)
    assert MediaRepository(conn).count() == 2

    (lib_dir / "movie2.mkv").unlink()

    result = sync_location(conn, lib_dir)
    assert result.files_missing == 1
    missing = MediaRepository(conn).get_missing()
    assert len(missing) == 1
    assert missing[0].filename == "movie2.mkv"


def test_sync_file_returns_after_missing(tmp_path: Path) -> None:
    conn = _make_connection()
    lib_dir = tmp_path / "library"
    lib_dir.mkdir()
    (lib_dir / "movie.mkv").write_bytes(b"")

    sync_location(conn, lib_dir)
    (lib_dir / "movie.mkv").unlink()

    sync_location(conn, lib_dir)
    assert len(MediaRepository(conn).get_missing()) == 1

    (lib_dir / "movie.mkv").write_bytes(b"new content")
    sync_location(conn, lib_dir)
    assert len(MediaRepository(conn).get_missing()) == 0
    assert MediaRepository(conn).count() == 1
