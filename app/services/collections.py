from __future__ import annotations

from app.library.collections_repository import (
    Collection,
    CollectionItem,
    CollectionsRepository,
)


class CollectionsService:
    """UI-facing API for user-defined collections."""

    def __init__(self, repository: CollectionsRepository) -> None:
        self._repo = repository

    @property
    def repository(self) -> CollectionsRepository:
        return self._repo

    def create(self, name: str, description: str | None = None) -> Collection:
        return self._repo.create(name, description)

    def get_or_create(
        self, name: str, description: str | None = None
    ) -> Collection:
        return self._repo.get(self._repo.get_collection(name, description))

    def get(self, collection_id: int) -> Collection | None:
        return self._repo.get(collection_id)

    def list(self) -> list[Collection]:
        return self._repo.list()

    def rename(self, collection_id: int, new_name: str) -> Collection:
        return self._repo.rename(collection_id, new_name)

    def update_description(self, collection_id: int, description: str | None) -> Collection:
        return self._repo.update_description(collection_id, description)

    def delete(self, collection_id: int) -> bool:
        return self._repo.delete(collection_id)

    def add_item(
        self, collection_id: int, entity_type: str, entity_id: int
    ) -> bool:
        return self._repo.add_item(collection_id, entity_type, entity_id)

    def remove_item(
        self, collection_id: int, entity_type: str, entity_id: int
    ) -> bool:
        return self._repo.remove_item(collection_id, entity_type, entity_id)

    def list_items(self, collection_id: int) -> list[CollectionItem]:
        return self._repo.list_items(collection_id)

    def contains(self, collection_id: int, entity_type: str, entity_id: int) -> bool:
        return self._repo.contains(collection_id, entity_type, entity_id)

    def count_items(self, collection_id: int) -> int:
        return self._repo.count_items(collection_id)
