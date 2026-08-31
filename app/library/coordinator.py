from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field

from app.domain.media import MediaFile
from app.library.scanner import ScanResult, ScanStats, scan_directory
from app.library.media_repository import MediaRepository

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SyncResult:
    files_added: int = 0
    files_updated: int = 0
    files_missing: int = 0
    files_recovered: int = 0
    scan_stats: ScanStats = field(default_factory=ScanStats)


@dataclass(slots=True)
class MetadataProcessResult:
    files_processed: int = 0
    entities_created: int = 0
    entities_reused: int = 0
    metadata_fetched: int = 0
    metadata_skipped: int = 0
    errors: list[str] = field(default_factory=list)


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


def process_library_metadata(
    connection: sqlite3.Connection,
    *,
    integration,
    parent_parts: list[str] | None = None,
) -> MetadataProcessResult:
    """Process metadata for all media files in the library.

    For each media file:
    1. Run identification to produce an IdentificationResult
    2. Process through LibraryMetadataIntegration
    3. Link media file to the resolved movie/tv entity

    This function is idempotent: running it twice produces the same result.
    """
    from app.metadata.identifier import identify
    from app.library.scanner import ScanResult as SR

    media_repo = MediaRepository(connection)
    result = MetadataProcessResult()

    all_files = media_repo.list_all()

    for mf in all_files:
        if mf.id is None:
            continue

        try:
            scan_result = SR(
                path=Path(mf.path),
                filename=mf.filename,
                extension=mf.extension or "",
                size_bytes=mf.size_bytes,
            )

            id_result = identify(scan_result, parent_parts=parent_parts)

            lib_result = integration.process_identification(id_result)

            result.files_processed += 1

            if lib_result.resolution.created:
                result.entities_created += 1
            else:
                result.entities_reused += 1

            if lib_result.metadata_fetched:
                result.metadata_fetched += 1
            else:
                result.metadata_skipped += 1

            _link_media_file(
                connection=connection,
                media_file_id=mf.id,
                entity_type=lib_result.resolution.entity_type,
                entity_id=lib_result.resolution.entity_id,
                season=id_result.season,
                episode=id_result.episode,
            )

        except Exception:
            logger.warning(
                "Failed to process metadata for %s",
                mf.path,
                exc_info=True,
            )
            result.errors.append(mf.path)

    return result


def _link_media_file(
    connection: sqlite3.Connection,
    media_file_id: int,
    entity_type: str,
    entity_id: int,
    *,
    season: int | None = None,
    episode: int | None = None,
) -> None:
    """Link a media file to its movie or TV entity."""
    if entity_type == "movie":
        connection.execute(
            """
            INSERT OR IGNORE INTO movie_files(movie_id, media_file_id)
            VALUES (?, ?)
            """,
            (entity_id, media_file_id),
        )
        connection.commit()
    elif entity_type == "tv":
        _link_tv_media_file(
            connection=connection,
            tv_show_id=entity_id,
            media_file_id=media_file_id,
            season=season,
            episode=episode,
        )


def _link_tv_media_file(
    connection: sqlite3.Connection,
    tv_show_id: int,
    media_file_id: int,
    *,
    season: int | None = None,
    episode: int | None = None,
) -> None:
    """Link a media file to a TV show episode.

    Uses actual season/episode numbers from identification when available.
    Falls back to season=1, episode=1 when not available.
    """
    season_num = season if season is not None else 1
    episode_num = episode if episode is not None else 1

    season_row = connection.execute(
        "SELECT id FROM seasons WHERE tv_show_id = ? AND season_number = ?",
        (tv_show_id, season_num),
    ).fetchone()

    if season_row is None:
        connection.execute(
            "INSERT INTO seasons(tv_show_id, season_number) VALUES (?, ?)",
            (tv_show_id, season_num),
        )
        connection.commit()
        season_row = connection.execute(
            "SELECT id FROM seasons WHERE tv_show_id = ? AND season_number = ?",
            (tv_show_id, season_num),
        ).fetchone()

    if season_row is not None:
        episode_row = connection.execute(
            """
            SELECT id FROM episodes
            WHERE season_id = ? AND episode_number = ?
            """,
            (season_row["id"], episode_num),
        ).fetchone()

        if episode_row is None:
            connection.execute(
                """
                INSERT INTO episodes(season_id, episode_number, title)
                VALUES (?, ?, 'Unknown')
                """,
                (season_row["id"], episode_num),
            )
            connection.commit()
            episode_row = connection.execute(
                """
                SELECT id FROM episodes
                WHERE season_id = ? AND episode_number = ?
                """,
                (season_row["id"], episode_num),
            ).fetchone()

        if episode_row is not None:
            connection.execute(
                """
                INSERT OR IGNORE INTO episode_files(episode_id, media_file_id)
                VALUES (?, ?)
                """,
                (episode_row["id"], media_file_id),
            )
            connection.commit()
