from __future__ import annotations

import sqlite3
from pathlib import Path


class LibraryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add_location(self, path: Path, label: str | None = None) -> int:
        resolved = str(path.resolve())
        cursor = self._conn.execute(
            "INSERT INTO library_locations(path, label) VALUES (?, ?)",
            (resolved, label),
        )
        self._conn.commit()
        return cursor.lastrowid

    def list_locations(self) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT id, path, label, added_at FROM library_locations ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]

    def remove_location(self, location_id: int) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM library_locations WHERE id = ?", (location_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def get_location_path(self, location_id: int) -> Path | None:
        row = self._conn.execute(
            "SELECT path FROM library_locations WHERE id = ?", (location_id,)
        ).fetchone()
        return Path(row["path"]) if row else None
