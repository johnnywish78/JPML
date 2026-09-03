from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.library.entity_types import ENTITY_TABLES, VALID_ENTITY_TYPES, validate_entity


@dataclass(frozen=True, slots=True)
class FavoriteEntry:
    entity_type: str
    entity_id: int
    added_at: str


class FavoritesRepository:
    """Persistence for favorite entities.

    Entities are identified by (entity_type, entity_id). The backing table is
    generic on purpose, so existence and cleanup are handled explicitly via
    ENTITY_TABLES rather than foreign keys.
    """

    TABLE = "favorites"

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def add(self, entity_type: str, entity_id: int) -> None:
        validate_entity(entity_type, entity_id)
        self._conn.execute(
            f"INSERT OR IGNORE INTO {self.TABLE}(entity_type, entity_id) VALUES (?, ?)",
            (entity_type, entity_id),
        )
        self._conn.commit()

    def remove(self, entity_type: str, entity_id: int) -> bool:
        validate_entity(entity_type, entity_id)
        cursor = self._conn.execute(
            f"DELETE FROM {self.TABLE} WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def is_favorite(self, entity_type: str, entity_id: int) -> bool:
        validate_entity(entity_type, entity_id)
        row = self._conn.execute(
            f"SELECT 1 FROM {self.TABLE} WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        ).fetchone()
        return row is not None

    def list(self, entity_type: str | None = None) -> list[FavoriteEntry]:
        if entity_type is None:
            rows = self._conn.execute(
                f"SELECT entity_type, entity_id, added_at FROM {self.TABLE} "
                "ORDER BY added_at, entity_type, entity_id"
            ).fetchall()
        else:
            if entity_type not in VALID_ENTITY_TYPES:
                raise ValueError(f"Unknown entity_type: {entity_type!r}")
            rows = self._conn.execute(
                f"SELECT entity_type, entity_id, added_at FROM {self.TABLE} "
                "WHERE entity_type = ? ORDER BY added_at, entity_id",
                (entity_type,),
            ).fetchall()
        return [
            FavoriteEntry(
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                added_at=row["added_at"],
            )
            for row in rows
        ]

    def get(self, entity_type: str, entity_id: int) -> FavoriteEntry | None:
        validate_entity(entity_type, entity_id)
        row = self._conn.execute(
            f"SELECT entity_type, entity_id, added_at FROM {self.TABLE} "
            "WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        ).fetchone()
        if row is None:
            return None
        return FavoriteEntry(
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            added_at=row["added_at"],
        )

    def prune_invalid(self) -> int:
        """Remove favorites whose entity no longer exists. Returns count removed."""
        removed = 0
        for entity_type, table in ENTITY_TABLES.items():
            cursor = self._conn.execute(
                f"""
                DELETE FROM {self.TABLE}
                WHERE entity_type = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM {table} AS t WHERE t.id = {self.TABLE}.entity_id
                  )
                """,
                (entity_type,),
            )
            removed += cursor.rowcount
        self._conn.commit()
        return removed
