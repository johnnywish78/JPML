from __future__ import annotations

import sqlite3

import pytest

from app.database.schema import initialize
from app.library.collections_repository import CollectionsRepository
from app.services.collections import CollectionsService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


class TestCollectionsRepository:
    def test_create_get_list(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        c = repo.create("Horror", "scary stuff")
        assert c.name == "Horror"
        assert c.description == "scary stuff"
        assert c.id > 0
        assert repo.get(c.id) is not None

        repo.create("Weekend")
        names = [c.name for c in repo.list()]
        assert names == ["Horror", "Weekend"]  # sorted by name

    def test_create_empty_name_raises(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        with pytest.raises(ValueError):
            repo.create("   ")

    def test_duplicate_name_raises(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        repo.create("Dup")
        with pytest.raises(ValueError):
            repo.create("Dup")

    def test_get_missing_returns_none(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        assert repo.get(999) is None

    def test_rename(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        c = repo.create("Old Name")
        renamed = repo.rename(c.id, "New Name")
        assert renamed.name == "New Name"
        with pytest.raises(ValueError):
            repo.rename(c.id, "   ")
        with pytest.raises(LookupError):
            repo.rename(999, "X")

    def test_rename_conflict_raises(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        a = repo.create("A")
        repo.create("B")
        with pytest.raises(ValueError):
            repo.rename(a.id, "B")

    def test_items_lifecycle(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        c = repo.create("C")
        assert repo.add_item(c.id, "movie", 1) is True
        assert repo.add_item(c.id, "movie", 1) is False  # duplicate
        assert repo.add_item(c.id, "movie", 2) is True
        assert repo.contains(c.id, "movie", 1) is True
        assert repo.contains(c.id, "movie", 3) is False

        items = repo.list_items(c.id)
        assert [i.entity_id for i in items] == [1, 2]
        assert repo.count_items(c.id) == 2

        assert repo.remove_item(c.id, "movie", 1) is True
        assert repo.remove_item(c.id, "movie", 1) is False
        assert repo.count_items(c.id) == 1

    def test_item_operations_require_existing_collection(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        with pytest.raises(LookupError):
            repo.add_item(999, "movie", 1)
        with pytest.raises(LookupError):
            repo.remove_item(999, "movie", 1)
        with pytest.raises(LookupError):
            repo.list_items(999)
        with pytest.raises(LookupError):
            repo.contains(999, "movie", 1)

    def test_add_item_invalid_entity_raises(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        c = repo.create("C")
        with pytest.raises(ValueError):
            repo.add_item(c.id, "bogus", 1)
        with pytest.raises(ValueError):
            repo.add_item(c.id, "movie", 0)

    def test_delete_cascades_items(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        c = repo.create("C")
        repo.add_item(c.id, "movie", 1)
        repo.add_item(c.id, "tv", 1)
        assert repo.delete(c.id) is True
        assert repo.delete(c.id) is False
        count = conn.execute(
            "SELECT COUNT(*) FROM collection_items WHERE collection_id = ?",
            (c.id,),
        ).fetchone()[0]
        assert count == 0
        assert repo.get(c.id) is None

    def test_delete_missing_returns_false(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        assert repo.delete(999) is False

    def test_get_or_create_idempotent(self) -> None:
        conn = _connection()
        repo = CollectionsRepository(conn)
        first = repo.get(repo.get_collection("Same"))
        second = repo.get(repo.get_collection("Same"))
        assert first.id == second.id
        count = conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
        assert count == 1


class TestCollectionsService:
    def test_service_roundtrip(self) -> None:
        conn = _connection()
        svc = CollectionsService(CollectionsRepository(conn))
        c = svc.create("Marvel")
        with pytest.raises(ValueError):
            svc.create("Marvel")

        assert svc.add_item(c.id, "movie", 42) is True
        assert svc.contains(c.id, "movie", 42) is True
        assert len(svc.list_items(c.id)) == 1
        assert svc.rename(c.id, "Marvel Studios").name == "Marvel Studios"
        assert svc.update_description(c.id, "heroes").description == "heroes"
        assert svc.count_items(c.id) == 1
        assert svc.delete(c.id) is True
        assert svc.get(c.id) is None

    def test_service_get_or_create(self) -> None:
        conn = _connection()
        svc = CollectionsService(CollectionsRepository(conn))
        c1 = svc.get_or_create("Nolan")
        c2 = svc.get_or_create("Nolan")
        assert c1.id == c2.id
