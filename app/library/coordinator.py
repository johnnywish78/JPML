from __future__ import annotations

import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

from app.domain.media import MediaFile
from app.library.scanner import ScanResult, ScanStats, scan_directory
from app.library.media_repository import MediaRepository


@dataclass(slots=True)
class SyncResult:
    files_added: int = 0
    files_updated: int = 0
    files_missing: int = 0
    files_recovered: int = 0
    scan_stats: ScanStats = field(default_factory=ScanStats)


def sync_location(
    connection: sqlite3.Connection,
    location_path: Path,
) -> SyncResult:
    resolved = location_path.resolve()
    media_repo = MediaRepository(connection)
    result = SyncResult()

    if not resolved.is_dir():
        result.scan_stats.errors.append(
            f"Location does not exist or is not a directory: {resolved}"
        )
        return result

    scan_results = scan_directory(resolved)
    result.scan_stats.media_files_found = len(scan_results)

    scanned_paths: set[str] = set()
    for sr in scan_results:
        abs_path = str(sr.path.resolve())
        scanned_paths.add(abs_path)
        media_file = MediaFile(
            path=abs_path,
            filename=sr.filename,
            extension=sr.extension,
            size_bytes=sr.size_bytes,
        )
        existing = media_repo.get_by_path(sr.path)
        if existing:
            media_repo.upsert(media_file)
            result.files_updated += 1
        else:
            media_repo.upsert(media_file)
            result.files_added += 1

    existing_files = media_repo.list_all()
    for mf in existing_files:
        if mf.id is not None and mf.path not in scanned_paths:
            media_repo.mark_missing(mf.id)
            result.files_missing += 1

    return result
