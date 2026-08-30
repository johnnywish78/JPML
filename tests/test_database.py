from __future__ import annotations

import sqlite3

from app.database.schema import initialize


def test_database_schema_and_foreign_keys() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    initialize(connection)

    tables = {
        row["name"]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }

    assert "movies" in tables
    assert "tv_shows" in tables
    assert "episodes" in tables
    assert "media_files" in tables
    assert "playback_state" in tables

    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    assert foreign_keys == 1


def test_relationships_and_transaction() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    initialize(connection)

    connection.execute(
        "INSERT INTO movies(title, year) VALUES (?, ?)",
        ("Test Movie", 2026),
    )

    movie_id = connection.execute(
        "SELECT id FROM movies WHERE title = ?",
        ("Test Movie",),
    ).fetchone()[0]

    connection.execute(
        """
        INSERT INTO media_files(path, filename)
        VALUES (?, ?)
        """,
        ("/tmp/test.mkv", "test.mkv"),
    )

    media_file_id = connection.execute(
        "SELECT id FROM media_files WHERE path = ?",
        ("/tmp/test.mkv",),
    ).fetchone()[0]

    connection.execute(
        """
        INSERT INTO movie_files(movie_id, media_file_id)
        VALUES (?, ?)
        """,
        (movie_id, media_file_id),
    )

    connection.commit()

    row = connection.execute(
        """
        SELECT m.title, f.filename
        FROM movies m
        JOIN movie_files mf ON mf.movie_id = m.id
        JOIN media_files f ON f.id = mf.media_file_id
        """
    ).fetchone()

    assert row["title"] == "Test Movie"
    assert row["filename"] == "test.mkv"


def test_foreign_key_rejects_invalid_reference() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    initialize(connection)

    try:
        connection.execute(
            """
            INSERT INTO movie_files(movie_id, media_file_id)
            VALUES (999, 999)
            """
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Foreign key constraint was not enforced")
