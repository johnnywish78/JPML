from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.database.schema import initialize
from app.library.favorites_repository import FavoritesRepository
from app.services.favorites import FavoritesService


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


class TestFavoritesRepository:
    def test_add_and_is_favorite(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        conn.execute("INSERT INTO movies(title) VALUES (?)", ("Inception",))
        conn.execute("INSERT INTO media_files(path, filename) VALUES (?, ?)",
                     ("/m/inception.mkv", "inception.mkv"))
        conn.commit()
        movie_id = conn.execute(
            "SELECT id FROM movies WHERE title = 'Inception'"
        ).fetchone()[0]

        assert repo.is_favorite("movie", movie_id) is False
        repo.add("movie", movie_id)
        assert repo.is_favorite("movie", movie_id) is True

    def test_duplicate_add_is_safe(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        conn.execute(
            "INSERT INTO movies(id, title) VALUES (1, 'X')"
        )
        conn.commit()
        repo.add("movie", 1)
        repo.add("movie", 1)
        count = conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE entity_type = 'movie'"
        ).fetchone()[0]
        assert count == 1

    def test_remove_is_idempotent(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'X')")
        conn.commit()
        repo.add("movie", 1)
        assert repo.remove("movie", 1) is True
        assert repo.remove("movie", 1) is False
        assert repo.is_favorite("movie", 1) is False

    def test_list_deterministic_ordering(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        for i, title in enumerate(["Zed", "Alpha", "Mid"], start=1):
            conn.execute(
                "INSERT INTO movies(id, title) VALUES (?, ?)", (i, title)
            )
        conn.commit()
        repo.add("movie", 3)  # Mid
        repo.add("movie", 1)  # Zed
        repo.add("movie", 2)  # Alpha
        repo.add("tv", 999)

        all_entries = repo.list()
        # deterministic order: added_at, entity_type, entity_id — entries
        # created in the same second order by entity_id
        assert [e.entity_id for e in all_entries if e.entity_type == "movie"] == [
            1, 2, 3
        ]
        assert all(e.added_at for e in all_entries)

        movie_only = repo.list("movie")
        assert all(e.entity_type == "movie" for e in movie_only)
        assert len(movie_only) == 3

    def test_get_returns_entry_with_timestamp(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'X')")
        conn.commit()
        repo.add("movie", 1)
        entry = repo.get("movie", 1)
        assert entry is not None
        assert entry.entity_type == "movie"
        assert entry.entity_id == 1
        assert entry.added_at
        assert repo.get("movie", 2) is None

    def test_invalid_entity_type_raises(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        with pytest.raises(ValueError):
            repo.add("bogus", 1)
        with pytest.raises(ValueError):
            repo.remove("bogus", 1)
        with pytest.raises(ValueError):
            repo.is_favorite("bogus", 1)

    def test_invalid_entity_id_raises(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        with pytest.raises(ValueError):
            repo.add("movie", 0)
        with pytest.raises(ValueError):
            repo.add("movie", -5)
        with pytest.raises(ValueError):
            repo.add("movie", "1")  # type: ignore[arg-type]

    def test_list_invalid_type_raises(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        with pytest.raises(ValueError):
            repo.list("bogus")

    def test_prune_invalid_removes_orphans(self) -> None:
        conn = _connection()
        repo = FavoritesRepository(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'Keep')")
        conn.execute("INSERT INTO movies(id, title) VALUES (2, 'Doomed')")
        conn.execute(
            "INSERT INTO media_files(id, path, filename) VALUES (7, '/a.mkv', 'a.mkv')"
        )
        conn.commit()
        repo.add("movie", 1)
        repo.add("movie", 2)
        with pytest.raises(ValueError):
            repo.add("media_file", 7)  # not a valid entity type
        repo.add("album", 4242)  # album that does not exist

        assert conn.execute("DELETE FROM movies WHERE id = 2").rowcount == 1
        conn.commit()

        removed = repo.prune_invalid()
        assert removed >= 2  # movie 2 + album 4242
        assert repo.is_favorite("movie", 1) is True
        assert repo.is_favorite("movie", 2) is False
        assert repo.is_favorite("album", 4242) is False


class TestFavoritesService:
    def _service(self, conn: sqlite3.Connection) -> FavoritesService:
        return FavoritesService(FavoritesRepository(conn))

    def test_service_add_rejects_missing_entity(self) -> None:
        conn = _connection()
        svc = self._service(conn)
        with pytest.raises(LookupError):
            svc.add("movie", 999)

    def test_service_add_rejects_unknown_type(self) -> None:
        conn = _connection()
        svc = self._service(conn)
        with pytest.raises(ValueError):
            svc.add("bogus", 1)

    def test_service_full_roundtrip(self) -> None:
        conn = _connection()
        svc = self._service(conn)
        conn.execute("INSERT INTO movies(id, title) VALUES (1, 'A')")
        conn.commit()
        svc.add("movie", 1)
        svc.add("movie", 1)  # idempotent
        assert svc.is_favorite("movie", 1) is True
        entries = svc.list("movie")
        assert len(entries) == 1
        assert svc.remove("movie", 1) is True
        assert svc.is_favorite("movie", 1) is False

    def test_persistence_across_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "persist.db"
            path = db_path.as_uri()

            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            initialize(conn)
            conn.execute("INSERT INTO movies(id, title) VALUES (1, 'A')")
            conn.commit()
            FavoritesService(FavoritesRepository(conn)).add("movie", 1)
            conn.close()

            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            initialize(conn)
            assert FavoritesService(FavoritesRepository(conn)).is_favorite(
                "movie", 1
            ) is True
            conn.close()
