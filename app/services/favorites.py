from __future__ import annotations

from app.library.entity_types import ENTITY_TABLES
from app.library.favorites_repository import FavoriteEntry, FavoritesRepository


class FavoritesService:
    """UI-facing API for favorites. All persistence goes through
    FavoritesRepository; callers never execute raw SQL."""

    def __init__(self, repository: FavoritesRepository) -> None:
        self._repo = repository

    @property
    def repository(self) -> FavoritesRepository:
        return self._repo

    def add(self, entity_type: str, entity_id: int) -> None:
        self._ensure_exists(entity_type, entity_id)
        self._repo.add(entity_type, entity_id)

    def remove(self, entity_type: str, entity_id: int) -> bool:
        return self._repo.remove(entity_type, entity_id)

    def is_favorite(self, entity_type: str, entity_id: int) -> bool:
        return self._repo.is_favorite(entity_type, entity_id)

    def list(self, entity_type: str | None = None) -> list[FavoriteEntry]:
        return self._repo.list(entity_type)

    def get(self, entity_type: str, entity_id: int) -> FavoriteEntry | None:
        return self._repo.get(entity_type, entity_id)

    def prune_invalid(self) -> int:
        return self._repo.prune_invalid()

    def _ensure_exists(self, entity_type: str, entity_id: int) -> None:
        table = ENTITY_TABLES.get(entity_type)
        if table is None:
            raise ValueError(f"Unknown entity_type: {entity_type!r}")
        row = self._repo.connection.execute(
            f"SELECT 1 FROM {table} WHERE id = ?", (entity_id,)
        ).fetchone()
        if row is None:
            raise LookupError(
                f"{entity_type} not found: id={entity_id}"
            )
