from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.library.scanner import (
    MEDIA_EXTENSIONS,
    ScanResult,
    is_media_file,
    scan_directory,
    scan_locations,
)


# ─── 1. Media extension detection ────────────────────────────────────────────

def test_video_extensions_detected(tmp_path: Path) -> None:
    for ext in [".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm", ".ts", ".m2ts"]:
        f = tmp_path / f"test{ext}"
        f.write_bytes(b"")
        assert is_media_file(f), f"Failed to detect {ext}"


def test_audio_extensions_detected(tmp_path: Path) -> None:
    for ext in [".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"]:
        f = tmp_path / f"test{ext}"
        f.write_bytes(b"")
        assert is_media_file(f), f"Failed to detect {ext}"


def test_non_media_file_not_detected(tmp_path: Path) -> None:
    for ext in [".txt", ".jpg", ".png", ".srt", ".sub", ".py", ".json", ".xml"]:
        f = tmp_path / f"test{ext}"
        f.write_bytes(b"")
        assert not is_media_file(f), f"Should not detect {ext} as media"


# ─── 2. Case-insensitive extension detection ─────────────────────────────────

def test_case_insensitive_extensions(tmp_path: Path) -> None:
    for name in ["movie.MKV", "movie.Mkv", "movie.mkv", "MOVIE.Mp4", "song.FLAC", "song.Flac"]:
        f = tmp_path / name
        f.write_bytes(b"")
        assert is_media_file(f), f"Failed case-insensitive detection for {name}"


# ─── 3. Recursive directory scanning ─────────────────────────────────────────

def test_recursive_scanning(tmp_path: Path) -> None:
    (tmp_path / "movie1.mkv").write_bytes(b"")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / "movie2.mp4").write_bytes(b"")
    deep = sub / "deep"
    deep.mkdir()
    (deep / "movie3.avi").write_bytes(b"")

    results = scan_directory(tmp_path)
    names = {r.filename for r in results}
    assert names == {"movie1.mkv", "movie2.mp4", "movie3.avi"}


# ─── 4. Ignored non-media files ──────────────────────────────────────────────

def test_non_media_files_ignored(tmp_path: Path) -> None:
    (tmp_path / "readme.txt").write_bytes(b"")
    (tmp_path / "poster.jpg").write_bytes(b"")
    (tmp_path / "subtitle.srt").write_bytes(b"")
    (tmp_path / "movie.mkv").write_bytes(b"")

    results = scan_directory(tmp_path)
    assert len(results) == 1
    assert results[0].filename == "movie.mkv"


# ─── 5. File metadata extraction ─────────────────────────────────────────────

def test_file_metadata_extraction(tmp_path: Path) -> None:
    content = b"x" * 1024
    f = tmp_path / "test.mkv"
    f.write_bytes(content)

    results = scan_directory(tmp_path)
    assert len(results) == 1
    r = results[0]
    assert r.filename == "test.mkv"
    assert r.extension == ".mkv"
    assert r.size_bytes == 1024
    assert r.path == f.resolve()


# ─── 6. Path with spaces ─────────────────────────────────────────────────────

def test_path_with_spaces(tmp_path: Path) -> None:
    spaced_dir = tmp_path / "My Movies" / "Action"
    spaced_dir.mkdir(parents=True)
    f = spaced_dir / "Cool Movie.mkv"
    f.write_bytes(b"")

    results = scan_directory(tmp_path)
    assert len(results) == 1
    assert results[0].filename == "Cool Movie.mkv"
    assert "My Movies" in str(results[0].path)


# ─── 7. Symlink safety ──────────────────────────────────────────────────────

def test_scanner_does_not_follow_symlinks(tmp_path: Path) -> None:
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    (real_dir / "movie.mkv").write_bytes(b"")

    link_dir = tmp_path / "link"
    link_dir.symlink_to(real_dir)

    results_root = scan_directory(tmp_path)
    filenames = {r.filename for r in results_root}
    assert "movie.mkv" in filenames

    real_count = scan_directory(real_dir)
    link_count = scan_directory(link_dir)
    assert len(real_count) == len(link_count)


# ─── scan_locations tests ─────────────────────────────────────────────────────

def test_scan_locations(tmp_path: Path) -> None:
    loc1 = tmp_path / "loc1"
    loc1.mkdir()
    (loc1 / "a.mkv").write_bytes(b"")
    loc2 = tmp_path / "loc2"
    loc2.mkdir()
    (loc2 / "b.mp4").write_bytes(b"")

    results, stats = scan_locations([loc1, loc2])
    assert len(results) == 2
    assert stats.locations_scanned == 2
    assert stats.media_files_found == 2


def test_scan_locations_nonexistent(tmp_path: Path) -> None:
    fake = tmp_path / "does_not_exist"
    results, stats = scan_locations([fake])
    assert len(results) == 0
    assert stats.locations_scanned == 1
    assert len(stats.errors) == 1
