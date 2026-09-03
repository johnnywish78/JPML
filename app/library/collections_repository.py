from __future__ import annotations

import sqlite3
import sqlite3 as _sqlite3
from dataclasses import dataclass

from app.library.entity_types import validate_entity


@dataclass(frozen=True, slots=True)
class Collection:
    id: int
    name: str
    description: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class CollectionItem:
    collection_id: int
    entity_type: str
    entity_id: int
    added_at: str


class CollectionsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    # -- collections ---------------------------------------------------------

    def get_collection(self, name: str, description: str | None = None) -> int:
        name = name.strip()
        if not name:
            raise ValueError("collection name must not be empty")
        row = self._conn.execute(
            "SELECT id FROM collections WHERE name = ?", (name,)
        ).fetchone()
        if row is not None:
            return int(row["id"])
        cursor = self._conn.execute(
            "INSERT INTO collections(name, description) VALUES (?, ?)",
            (name, description),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def create(self, name: str, description: str | None = None) -> Collection:
        name = name.strip()
        if not name:
            raise ValueError("collection name must not be empty")
        try:
            cursor = self._conn.execute(
                "INSERT INTO collections(name, description) VALUES (?, ?)",
                (name, description),
            )
        except _sqlite3.IntegrityError as exc:
            raise ValueError(f"collection already exists: {name!r}") from exc
        self._conn.commit()
        return self.get(int(cursor.lastrowid))  # type: ignore[arg-type]

    def get(self, collection_id: int) -> Collection | None:
        row = self._conn.execute(
            "SELECT id, name, description, created_at, updated_at "
            "FROM collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
        if row is None:
            return None
        return Collection(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list(self) -> list[Collection]:
        rows = self._conn.execute(
            "SELECT id, name, description, created_at, updated_at "
            "FROM collections ORDER BY name"
        ).fetchall()
        return [
            Collection(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def rename(self, collection_id: int, new_name: str) -> Collection:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("collection name must not be empty")
        if self.get(collection_id) is None:
            raise LookupError(f"collection not found: {collection_id}")
        try:
            self._conn.execute(
                "UPDATE collections SET name = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (new_name, collection_id),
            )
        except _sqlite3.IntegrityError as exc:
            raise ValueError(f"collection already exists: {new_name!r}") from exc
        self._conn.commit()
        renamed = self.get(collection_id)
        assert renamed is not None
        return renamed

    def update_description(self, collection_id: int, description: str | None) -> Collection:
        if self.get(collection_id) is None:
            raise LookupError(f"collection not found: {collection_id}")
        self._conn.execute(
            "UPDATE collections SET description = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ?",
            (description, collection_id),
        )
        self._conn.commit()
        updated = self.get(collection_id)
        assert updated is not None
        return updated

    def delete(self, collection_id: int) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM collections WHERE id = ?", (collection_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # -- items ---------------------------------------------------------------

    def add_item(
        self, collection_id: int, entity_type: str, entity_id: int
    ) -> bool:
        """Add an entity to a collection. Returns False when already present."""
        validate_entity(entity_type, entity_id)
        if self.get(collection_id) is None:
            raise LookupError(f"collection not found: {collection_id}")
        cursor = self._conn.execute(
            "INSERT OR IGNORE INTO collection_items "
            "(collection_id, entity_type, entity_id) VALUES (?, ?, ?)",
            (collection_id, entity_type, entity_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def remove_item(
        self, collection_id: int, entity_type: str, entity_id: int
    ) -> bool:
        validate_entity(entity_type, entity_id)
        if self.get(collection_id) is None:
            raise LookupError(f"collection not found: {collection_id}")
        cursor = self._conn.execute(
            "DELETE FROM collection_items "
            "WHERE collection_id = ? AND entity_type = ? AND entity_id = ?",
            (collection_id, entity_type, entity_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def list_items(self, collection_id: int) -> list[CollectionItem]:
        if self.get(collection_id) is None:
            raise LookupError(f"collection not found: {collection_id}")
        rows = self._conn.execute(
            "SELECT collection_id, entity_type, entity_id, added_at "
            "FROM collection_items WHERE collection_id = ? "
            "ORDER BY added_at, entity_type, entity_id",
            (collection_id,),
        ).fetchall()
        return [
            CollectionItem(
                collection_id=row["collection_id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                added_at=row["added_at"],
            )
            for row in rows
        ]

    def contains(self, collection_id: int, entity_type: str, entity_id: int) -> bool:
        validate_entity(entity_type, entity_id)
        if self.get(collection_id) is None:
            raise LookupError(f"collection not found: {collection_id}")
        row = self._conn.execute(
            "SELECT 1 FROM collection_items "
            "WHERE collection_id = ? AND entity_type = ? AND entity_id = ?",
            (collection_id, entity_type, entity_id),
        ).fetchone()
        return row is not None

    def count_items(self, collection_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM collection_items WHERE collection_id = ?",
            (collection_id,),
        ).fetchone()
        return int(row["n"])
