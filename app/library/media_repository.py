from __future__ import annotations

import sqlite3
from pathlib import Path

from app.domain.media import MediaFile


class MediaRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def upsert(self, media_file: MediaFile) -> int:
        resolved_path = str(Path(media_file.path).resolve())
        existing = self._conn.execute(
            "SELECT id FROM media_files WHERE path = ?", (resolved_path,)
        ).fetchone()

        if existing:
            self._conn.execute(
                """
                UPDATE media_files
                SET filename = ?, extension = ?, size_bytes = ?,
                    is_missing = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    media_file.filename,
                    media_file.extension,
                    media_file.size_bytes,
                    existing["id"],
                ),
            )
            self._conn.commit()
            return existing["id"]

        cursor = self._conn.execute(
            """
            INSERT INTO media_files(path, filename, extension, size_bytes, is_missing)
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                resolved_path,
                media_file.filename,
                media_file.extension,
                media_file.size_bytes,
            ),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_by_path(self, path: Path) -> MediaFile | None:
        resolved = str(path.resolve())
        row = self._conn.execute(
            "SELECT * FROM media_files WHERE path = ?", (resolved,)
        ).fetchone()
        if row is None:
            return None
        return MediaFile(
            path=row["path"],
            filename=row["filename"],
            extension=row["extension"],
            size_bytes=row["size_bytes"],
            duration_seconds=row["duration_seconds"],
            mime_type=row["mime_type"],
            id=row["id"],
        )

    def list_all(self) -> list[MediaFile]:
        rows = self._conn.execute(
            "SELECT * FROM media_files ORDER BY path"
        ).fetchall()
        return [
            MediaFile(
                path=row["path"],
                filename=row["filename"],
                extension=row["extension"],
                size_bytes=row["size_bytes"],
                duration_seconds=row["duration_seconds"],
                mime_type=row["mime_type"],
                id=row["id"],
            )
            for row in rows
        ]

    def get_missing(self) -> list[MediaFile]:
        rows = self._conn.execute(
            "SELECT * FROM media_files WHERE is_missing = 1 ORDER BY path"
        ).fetchall()
        return [
            MediaFile(
                path=row["path"],
                filename=row["filename"],
                extension=row["extension"],
                size_bytes=row["size_bytes"],
                duration_seconds=row["duration_seconds"],
                mime_type=row["mime_type"],
                id=row["id"],
            )
            for row in rows
        ]

    def mark_missing(self, media_file_id: int) -> None:
        self._conn.execute(
            """
            UPDATE media_files
            SET is_missing = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (media_file_id,),
        )
        self._conn.commit()

    def mark_present(self, media_file_id: int) -> None:
        self._conn.execute(
            """
            UPDATE media_files
            SET is_missing = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (media_file_id,),
        )
        self._conn.commit()

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM media_files").fetchone()
        return row[0]

    def delete(self, media_file_id: int) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM media_files WHERE id = ?", (media_file_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0
