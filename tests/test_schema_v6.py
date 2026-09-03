from __future__ import annotations

import sqlite3

from app.database.schema import (
    SCHEMA_VERSION,
    _get_schema_version,
    initialize,
)


V6_TABLES = {
    "favorites",
    "watchlist",
    "collections",
    "collection_items",
    "artists",
    "albums",
    "music_tracks",
    "track_files",
}


def _fresh_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


class TestFreshDatabaseV6:
    def test_fresh_database_is_version_6(self) -> None:
        assert SCHEMA_VERSION == 6
        connection = _fresh_connection()
        initialize(connection)
        assert _get_schema_version(connection) == 6

    def test_all_v6_tables_exist(self) -> None:
        connection = _fresh_connection()
        initialize(connection)
        tables = _table_names(connection)
        assert V6_TABLES.issubset(tables)

    def test_sqlite_integrity_check(self) -> None:
        connection = _fresh_connection()
        initialize(connection)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            connection.execute("PRAGMA foreign_key_check").fetchone() is None
        )

    def test_initialize_idempotent_v6(self) -> None:
        connection = _fresh_connection()
        initialize(connection)
        initialize(connection)
        assert _get_schema_version(connection) == 6


class TestV5ToV6Migration:
    def _make_v5_database(self, connection: sqlite3.Connection) -> None:
        """Simulate a database at exactly schema version 5."""
        initialize(connection)  # build v6
        # remove the v6 additions
        for table in sorted(V6_TABLES):
            connection.execute(f"DROP TABLE {table}")
        connection.execute(
            "DELETE FROM schema_version WHERE version != 5"
        )
        connection.commit()

    def test_upgrade_from_v5(self) -> None:
        connection = _fresh_connection()
        self._make_v5_database(connection)
        assert _get_schema_version(connection) == 5
        assert not (V6_TABLES & _table_names(connection))

        initialize(connection)

        assert _get_schema_version(connection) == 6
        assert V6_TABLES.issubset(_table_names(connection))

    def test_upgrade_preserves_existing_data(self) -> None:
        connection = _fresh_connection()
        self._make_v5_database(connection)

        connection.execute(
            "INSERT INTO movies(id, title, year) VALUES (1, 'Inception', 2010)"
        )
        connection.execute(
            "INSERT INTO media_files(id, path, filename) "
            "VALUES (1, '/m/a.mkv', 'a.mkv')"
        )
        connection.execute(
            "INSERT INTO playback_history(media_type, media_id, file_path, "
            "started_at, last_position, duration, completed) "
            "VALUES ('movie', 1, '/m/a.mkv', '2026-01-01 00:00:00', 100.0, "
            "3600.0, 1)"
        )
        connection.commit()

        initialize(connection)

        assert connection.execute(
            "SELECT title FROM movies WHERE id = 1"
        ).fetchone()["title"] == "Inception"
        assert connection.execute("SELECT COUNT(*) FROM media_files").fetchone()[0] == 1
        row = connection.execute("SELECT last_position FROM playback_history").fetchone()
        assert row[0] == 100.0

    def test_upgrade_full_migration_path_v1(self) -> None:
        """A database starting at v1 reaches v6 through all migrations."""
        connection = _fresh_connection()

        # build the v1 base schema shape: run full init then roll back the
        # migration-added tables and set version to 1
        initialize(connection)
        for table in ("playback_history", "favorites", "watchlist",
                      "collections", "collection_items", "artists", "albums",
                      "music_tracks", "track_files", "external_ids",
                      "artwork", "metadata_sources", "genres", "movie_genres",
                      "tv_genres"):
            connection.execute(f"DROP TABLE IF EXISTS {table}")
        try:
            connection.execute(
                "ALTER TABLE media_files DROP COLUMN is_missing"
            )
        except sqlite3.OperationalError:
            pass
        connection.execute("DELETE FROM schema_version WHERE version != 1")
        connection.commit()
        assert _get_schema_version(connection) == 1

        connection.execute("INSERT INTO movies(id, title) VALUES (1, 'X')")
        connection.commit()

        initialize(connection)

        assert _get_schema_version(connection) == 6
        assert V6_TABLES.issubset(_table_names(connection))
        assert "playback_history" in _table_names(connection)
        assert connection.execute("SELECT title FROM movies").fetchone()[0] == "X"
