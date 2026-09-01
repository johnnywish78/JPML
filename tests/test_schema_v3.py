from __future__ import annotations

import sqlite3

from app.database.schema import SCHEMA_VERSION, _get_schema_version, _migrate_v1_to_v2, _migrate_v2_to_v3, initialize


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


# ── 1. Fresh database creates all v3 tables ──────────────────────────────────

def test_fresh_database_creates_all_v3_tables() -> None:
    connection = _fresh_connection()
    initialize(connection)

    tables = _table_names(connection)
    expected = {
        "schema_version", "movies", "tv_shows", "seasons", "episodes",
        "people", "movie_people", "tv_people", "library_locations",
        "media_files", "movie_files", "episode_files", "playback_state",
        "external_ids", "artwork", "metadata_sources", "genres",
        "movie_genres", "tv_genres",
    }
    assert expected.issubset(tables)


# ── 2. Schema version is 3 ──────────────────────────────────────────────────

def test_schema_version_is_3() -> None:
    assert SCHEMA_VERSION == 4

    connection = _fresh_connection()
    initialize(connection)

    version = _get_schema_version(connection)
    assert version == 4


# ── 3. v2 database migrates to v3 ────────────────────────────────────────────

def _build_v2_database(connection: sqlite3.Connection) -> None:
    """Construct a schema at exactly v2 level."""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            original_title TEXT,
            year INTEGER,
            overview TEXT,
            runtime_minutes INTEGER,
            imdb_id TEXT UNIQUE,
            tmdb_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tv_shows (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            original_title TEXT,
            year INTEGER,
            overview TEXT,
            imdb_id TEXT UNIQUE,
            tmdb_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY,
            tv_show_id INTEGER NOT NULL,
            season_number INTEGER NOT NULL,
            title TEXT,
            overview TEXT,
            UNIQUE(tv_show_id, season_number),
            FOREIGN KEY (tv_show_id)
                REFERENCES tv_shows(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY,
            season_id INTEGER NOT NULL,
            episode_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            overview TEXT,
            air_date TEXT,
            imdb_id TEXT UNIQUE,
            tmdb_id INTEGER UNIQUE,
            UNIQUE(season_id, episode_number),
            FOREIGN KEY (season_id)
                REFERENCES seasons(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            biography TEXT,
            imdb_id TEXT UNIQUE,
            tmdb_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movie_people (
            movie_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            role TEXT,
            character_name TEXT,
            PRIMARY KEY(movie_id, person_id, role, character_name),
            FOREIGN KEY(movie_id)
                REFERENCES movies(id)
                ON DELETE CASCADE,
            FOREIGN KEY(person_id)
                REFERENCES people(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tv_people (
            tv_show_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            role TEXT,
            character_name TEXT,
            PRIMARY KEY(tv_show_id, person_id, role, character_name),
            FOREIGN KEY(tv_show_id)
                REFERENCES tv_shows(id)
                ON DELETE CASCADE,
            FOREIGN KEY(person_id)
                REFERENCES people(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS library_locations (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            label TEXT,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS media_files (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            extension TEXT,
            size_bytes INTEGER,
            duration_seconds REAL,
            mime_type TEXT,
            is_missing INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movie_files (
            movie_id INTEGER NOT NULL,
            media_file_id INTEGER NOT NULL,
            PRIMARY KEY(movie_id, media_file_id),
            FOREIGN KEY(movie_id)
                REFERENCES movies(id)
                ON DELETE CASCADE,
            FOREIGN KEY(media_file_id)
                REFERENCES media_files(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS episode_files (
            episode_id INTEGER NOT NULL,
            media_file_id INTEGER NOT NULL,
            PRIMARY KEY(episode_id, media_file_id),
            FOREIGN KEY(episode_id)
                REFERENCES episodes(id)
                ON DELETE CASCADE,
            FOREIGN KEY(media_file_id)
                REFERENCES media_files(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS playback_state (
            id INTEGER PRIMARY KEY,
            media_file_id INTEGER NOT NULL UNIQUE,
            position_seconds REAL NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(media_file_id)
                REFERENCES media_files(id)
                ON DELETE CASCADE
        );

        INSERT INTO schema_version(version) VALUES (2);
        """
    )
    connection.commit()


def test_v2_database_migrates_to_v3() -> None:
    connection = _fresh_connection()
    _build_v2_database(connection)

    assert _get_schema_version(connection) == 2

    _migrate_v2_to_v3(connection)

    assert _get_schema_version(connection) == 3
    tables = _table_names(connection)
    assert "external_ids" in tables
    assert "artwork" in tables
    assert "metadata_sources" in tables
    assert "genres" in tables
    assert "movie_genres" in tables
    assert "tv_genres" in tables


# ── 4. Existing v2 data survives migration ───────────────────────────────────

def test_v2_data_survives_migration_to_v3() -> None:
    connection = _fresh_connection()
    _build_v2_database(connection)

    connection.execute("INSERT INTO movies(title, year) VALUES (?, ?)", ("Inception", 2010))
    connection.execute("INSERT INTO people(name) VALUES (?)", ("Christopher Nolan",))
    connection.execute("INSERT INTO media_files(path, filename) VALUES (?, ?)", ("/m/inception.mkv", "inception.mkv"))
    connection.commit()

    _migrate_v2_to_v3(connection)

    assert connection.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM media_files").fetchone()[0] == 1

    movie = connection.execute("SELECT title, year FROM movies WHERE title = 'Inception'").fetchone()
    assert movie["title"] == "Inception"
    assert movie["year"] == 2010


# ── 5. external_ids accepts provider identities ──────────────────────────────

def test_external_ids_accepts_provider_identities() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Test Movie",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Test Movie'").fetchone()[0]

    connection.execute(
        "INSERT INTO external_ids(entity_type, entity_id, provider, external_id, is_primary) VALUES (?, ?, ?, ?, ?)",
        ("movie", movie_id, "tmdb", "12345", 1),
    )
    connection.commit()

    row = connection.execute(
        "SELECT provider, external_id, is_primary FROM external_ids WHERE entity_type = 'movie' AND entity_id = ?",
        (movie_id,),
    ).fetchone()
    assert row["provider"] == "tmdb"
    assert row["external_id"] == "12345"
    assert row["is_primary"] == 1


# ── 6. external_ids uniqueness prevents duplicate provider/entity mappings ────

def test_external_ids_no_duplicate_provider_entity() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Test Movie",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Test Movie'").fetchone()[0]

    connection.execute(
        "INSERT INTO external_ids(entity_type, entity_id, provider, external_id) VALUES (?, ?, ?, ?)",
        ("movie", movie_id, "tmdb", "12345"),
    )
    connection.commit()

    try:
        connection.execute(
            "INSERT INTO external_ids(entity_type, entity_id, provider, external_id) VALUES (?, ?, ?, ?)",
            ("movie", movie_id, "tmdb", "99999"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Duplicate (entity_type, entity_id, provider) was not rejected")


# ── 7. external_ids uniqueness prevents same provider ID for two entities ────

def test_external_ids_no_duplicate_provider_id_across_entities() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Movie A",))
    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Movie B",))
    ids = [row[0] for row in connection.execute("SELECT id FROM movies ORDER BY id").fetchall()]

    connection.execute(
        "INSERT INTO external_ids(entity_type, entity_id, provider, external_id) VALUES (?, ?, ?, ?)",
        ("movie", ids[0], "tmdb", "55555"),
    )
    connection.commit()

    try:
        connection.execute(
            "INSERT INTO external_ids(entity_type, entity_id, provider, external_id) VALUES (?, ?, ?, ?)",
            ("movie", ids[1], "tmdb", "55555"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Same provider external_id assigned to two entities was not rejected")


# ── 8. artwork records can be inserted ────────────────────────────────────────

def test_artwork_records_can_be_inserted() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Test Movie",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Test Movie'").fetchone()[0]

    connection.execute(
        "INSERT INTO artwork(entity_type, entity_id, artwork_type, provider, provider_path, local_path, width, height) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("movie", movie_id, "poster", "tmdb", "/poster/12345", "/cache/poster_12345.jpg", 500, 750),
    )
    connection.commit()

    row = connection.execute(
        "SELECT artwork_type, provider, local_path, width, height FROM artwork WHERE entity_id = ?",
        (movie_id,),
    ).fetchone()
    assert row["artwork_type"] == "poster"
    assert row["provider"] == "tmdb"
    assert row["local_path"] == "/cache/poster_12345.jpg"
    assert row["width"] == 500
    assert row["height"] == 750


# ── 9. artwork uniqueness works as designed ──────────────────────────────────

def test_artwork_uniqueness_prevents_duplicate_type() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Test Movie",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Test Movie'").fetchone()[0]

    connection.execute(
        "INSERT INTO artwork(entity_type, entity_id, artwork_type, provider, provider_path) VALUES (?, ?, ?, ?, ?)",
        ("movie", movie_id, "poster", "tmdb", "/p1"),
    )
    connection.commit()

    try:
        connection.execute(
            "INSERT INTO artwork(entity_type, entity_id, artwork_type, provider, provider_path) VALUES (?, ?, ?, ?, ?)",
            ("movie", movie_id, "poster", "tmdb", "/p2"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Duplicate artwork type/provider was not rejected")


def test_artwork_allows_same_type_different_providers() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Test Movie",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Test Movie'").fetchone()[0]

    connection.execute(
        "INSERT INTO artwork(entity_type, entity_id, artwork_type, provider, provider_path) VALUES (?, ?, ?, ?, ?)",
        ("movie", movie_id, "poster", "tmdb", "/p1"),
    )
    connection.execute(
        "INSERT INTO artwork(entity_type, entity_id, artwork_type, provider, provider_path) VALUES (?, ?, ?, ?, ?)",
        ("movie", movie_id, "poster", "imdb", "/p2"),
    )
    connection.commit()

    count = connection.execute(
        "SELECT COUNT(*) FROM artwork WHERE entity_type = 'movie' AND entity_id = ? AND artwork_type = 'poster'",
        (movie_id,),
    ).fetchone()[0]
    assert count == 2


# ── 10. metadata_sources records freshness fields ────────────────────────────

def test_metadata_sources_records_freshness_fields() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Test Movie",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Test Movie'").fetchone()[0]

    connection.execute(
        "INSERT INTO metadata_sources(entity_type, entity_id, provider, fetched_at, expires_at, metadata_version, user_override) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("movie", movie_id, "tmdb", "2026-01-01T00:00:00", "2026-02-01T00:00:00", "2.1", 0),
    )
    connection.commit()

    row = connection.execute(
        "SELECT provider, fetched_at, expires_at, metadata_version, user_override "
        "FROM metadata_sources WHERE entity_id = ?",
        (movie_id,),
    ).fetchone()
    assert row["provider"] == "tmdb"
    assert row["fetched_at"] == "2026-01-01T00:00:00"
    assert row["expires_at"] == "2026-02-01T00:00:00"
    assert row["metadata_version"] == "2.1"
    assert row["user_override"] == 0


# ── 11. metadata_sources uniqueness works ────────────────────────────────────

def test_metadata_sources_uniqueness() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Test Movie",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Test Movie'").fetchone()[0]

    connection.execute(
        "INSERT INTO metadata_sources(entity_type, entity_id, provider) VALUES (?, ?, ?)",
        ("movie", movie_id, "tmdb"),
    )
    connection.commit()

    try:
        connection.execute(
            "INSERT INTO metadata_sources(entity_type, entity_id, provider) VALUES (?, ?, ?)",
            ("movie", movie_id, "tmdb"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Duplicate metadata_sources entity/provider was not rejected")


# ── 12. genres are unique ────────────────────────────────────────────────────

def test_genres_are_unique() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO genres(name) VALUES (?)", ("Science Fiction",))
    connection.commit()

    try:
        connection.execute("INSERT INTO genres(name) VALUES (?)", ("Science Fiction",))
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Duplicate genre name was not rejected")


# ── 13. movie_genres links movie ↔ genre ─────────────────────────────────────

def test_movie_genres_links_movie_and_genre() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Inception",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Inception'").fetchone()[0]
    connection.execute("INSERT INTO genres(name) VALUES (?)", ("Science Fiction",))
    genre_id = connection.execute("SELECT id FROM genres WHERE name = 'Science Fiction'").fetchone()[0]

    connection.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (?, ?)", (movie_id, genre_id))
    connection.commit()

    row = connection.execute(
        "SELECT m.title, g.name "
        "FROM movie_genres mg "
        "JOIN movies m ON m.id = mg.movie_id "
        "JOIN genres g ON g.id = mg.genre_id "
        "WHERE mg.movie_id = ?",
        (movie_id,),
    ).fetchone()
    assert row["title"] == "Inception"
    assert row["name"] == "Science Fiction"


# ── 14. tv_genres links TV show ↔ genre ──────────────────────────────────────

def test_tv_genres_links_tv_show_and_genre() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO tv_shows(title) VALUES (?)", ("Breaking Bad",))
    show_id = connection.execute("SELECT id FROM tv_shows WHERE title = 'Breaking Bad'").fetchone()[0]
    connection.execute("INSERT INTO genres(name) VALUES (?)", ("Drama",))
    genre_id = connection.execute("SELECT id FROM genres WHERE name = 'Drama'").fetchone()[0]

    connection.execute("INSERT INTO tv_genres(tv_show_id, genre_id) VALUES (?, ?)", (show_id, genre_id))
    connection.commit()

    row = connection.execute(
        "SELECT t.title, g.name "
        "FROM tv_genres tg "
        "JOIN tv_shows t ON t.id = tg.tv_show_id "
        "JOIN genres g ON g.id = tg.genre_id "
        "WHERE tg.tv_show_id = ?",
        (show_id,),
    ).fetchone()
    assert row["title"] == "Breaking Bad"
    assert row["name"] == "Drama"


# ── 15. Cascading deletes work for movie_genres/tv_genres ────────────────────

def test_cascading_delete_movie_removes_movie_genres() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Delete Me",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Delete Me'").fetchone()[0]
    connection.execute("INSERT INTO genres(name) VALUES (?)", ("Action",))
    genre_id = connection.execute("SELECT id FROM genres WHERE name = 'Action'").fetchone()[0]
    connection.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (?, ?)", (movie_id, genre_id))
    connection.commit()

    assert connection.execute("SELECT COUNT(*) FROM movie_genres").fetchone()[0] == 1

    connection.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
    connection.commit()

    assert connection.execute("SELECT COUNT(*) FROM movie_genres").fetchone()[0] == 0


def test_cascading_delete_tv_show_removes_tv_genres() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO tv_shows(title) VALUES (?)", ("Delete Me Show",))
    show_id = connection.execute("SELECT id FROM tv_shows WHERE title = 'Delete Me Show'").fetchone()[0]
    connection.execute("INSERT INTO genres(name) VALUES (?)", ("Thriller",))
    genre_id = connection.execute("SELECT id FROM genres WHERE name = 'Thriller'").fetchone()[0]
    connection.execute("INSERT INTO tv_genres(tv_show_id, genre_id) VALUES (?, ?)", (show_id, genre_id))
    connection.commit()

    assert connection.execute("SELECT COUNT(*) FROM tv_genres").fetchone()[0] == 1

    connection.execute("DELETE FROM tv_shows WHERE id = ?", (show_id,))
    connection.commit()

    assert connection.execute("SELECT COUNT(*) FROM tv_genres").fetchone()[0] == 0


def test_cascading_delete_genre_removes_movie_genres() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Keep Me",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Keep Me'").fetchone()[0]
    connection.execute("INSERT INTO genres(name) VALUES (?)", ("Horror",))
    genre_id = connection.execute("SELECT id FROM genres WHERE name = 'Horror'").fetchone()[0]
    connection.execute("INSERT INTO movie_genres(movie_id, genre_id) VALUES (?, ?)", (movie_id, genre_id))
    connection.commit()

    assert connection.execute("SELECT COUNT(*) FROM movie_genres").fetchone()[0] == 1

    connection.execute("DELETE FROM genres WHERE id = ?", (genre_id,))
    connection.commit()

    assert connection.execute("SELECT COUNT(*) FROM movie_genres").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 1


def test_cascading_delete_genre_removes_tv_genres() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO tv_shows(title) VALUES (?)", ("Keep Me Show",))
    show_id = connection.execute("SELECT id FROM tv_shows WHERE title = 'Keep Me Show'").fetchone()[0]
    connection.execute("INSERT INTO genres(name) VALUES (?)", ("Comedy",))
    genre_id = connection.execute("SELECT id FROM genres WHERE name = 'Comedy'").fetchone()[0]
    connection.execute("INSERT INTO tv_genres(tv_show_id, genre_id) VALUES (?, ?)", (show_id, genre_id))
    connection.commit()

    assert connection.execute("SELECT COUNT(*) FROM tv_genres").fetchone()[0] == 1

    connection.execute("DELETE FROM genres WHERE id = ?", (genre_id,))
    connection.commit()

    assert connection.execute("SELECT COUNT(*) FROM tv_genres").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM tv_shows").fetchone()[0] == 1


# ── 16. Foreign-key enforcement remains enabled ──────────────────────────────

def test_foreign_keys_enforced_on_v3_tables() -> None:
    connection = _fresh_connection()
    initialize(connection)

    try:
        connection.execute(
            "INSERT INTO movie_genres(movie_id, genre_id) VALUES (?, ?)",
            (999, 999),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Foreign key constraint on movie_genres was not enforced")

    try:
        connection.execute(
            "INSERT INTO tv_genres(tv_show_id, genre_id) VALUES (?, ?)",
            (999, 999),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Foreign key constraint on tv_genres was not enforced")


def test_foreign_key_rejects_invalid_movie_reference() -> None:
    connection = _fresh_connection()
    initialize(connection)

    try:
        connection.execute(
            "INSERT INTO movie_files(movie_id, media_file_id) VALUES (999, 999)"
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Foreign key constraint was not enforced")


# ── 17. Existing v1/v2 migration tests remain green ──────────────────────────

def test_v1_to_v2_migration_still_works() -> None:
    """Verify that a v1 database can still migrate through to v3."""
    connection = _fresh_connection()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            original_title TEXT,
            year INTEGER,
            overview TEXT,
            runtime_minutes INTEGER,
            imdb_id TEXT UNIQUE,
            tmdb_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tv_shows (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            original_title TEXT,
            year INTEGER,
            overview TEXT,
            imdb_id TEXT UNIQUE,
            tmdb_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY,
            tv_show_id INTEGER NOT NULL,
            season_number INTEGER NOT NULL,
            title TEXT,
            overview TEXT,
            UNIQUE(tv_show_id, season_number),
            FOREIGN KEY (tv_show_id)
                REFERENCES tv_shows(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS episodes (
            id INTEGER PRIMARY KEY,
            season_id INTEGER NOT NULL,
            episode_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            overview TEXT,
            air_date TEXT,
            imdb_id TEXT UNIQUE,
            tmdb_id INTEGER UNIQUE,
            UNIQUE(season_id, episode_number),
            FOREIGN KEY (season_id)
                REFERENCES seasons(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            biography TEXT,
            imdb_id TEXT UNIQUE,
            tmdb_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movie_people (
            movie_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            role TEXT,
            character_name TEXT,
            PRIMARY KEY(movie_id, person_id, role, character_name),
            FOREIGN KEY(movie_id)
                REFERENCES movies(id)
                ON DELETE CASCADE,
            FOREIGN KEY(person_id)
                REFERENCES people(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tv_people (
            tv_show_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            role TEXT,
            character_name TEXT,
            PRIMARY KEY(tv_show_id, person_id, role, character_name),
            FOREIGN KEY(tv_show_id)
                REFERENCES tv_shows(id)
                ON DELETE CASCADE,
            FOREIGN KEY(person_id)
                REFERENCES people(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS media_files (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            extension TEXT,
            size_bytes INTEGER,
            duration_seconds REAL,
            mime_type TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS movie_files (
            movie_id INTEGER NOT NULL,
            media_file_id INTEGER NOT NULL,
            PRIMARY KEY(movie_id, media_file_id),
            FOREIGN KEY(movie_id)
                REFERENCES movies(id)
                ON DELETE CASCADE,
            FOREIGN KEY(media_file_id)
                REFERENCES media_files(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS episode_files (
            episode_id INTEGER NOT NULL,
            media_file_id INTEGER NOT NULL,
            PRIMARY KEY(episode_id, media_file_id),
            FOREIGN KEY(episode_id)
                REFERENCES episodes(id)
                ON DELETE CASCADE,
            FOREIGN KEY(media_file_id)
                REFERENCES media_files(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS playback_state (
            id INTEGER PRIMARY KEY,
            media_file_id INTEGER NOT NULL UNIQUE,
            position_seconds REAL NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(media_file_id)
                REFERENCES media_files(id)
                ON DELETE CASCADE
        );

        INSERT INTO schema_version(version) VALUES (1);
        """
    )
    connection.commit()

    assert _get_schema_version(connection) == 1

    _migrate_v1_to_v2(connection)
    assert _get_schema_version(connection) == 2

    _migrate_v2_to_v3(connection)
    assert _get_schema_version(connection) == 3

    tables = _table_names(connection)
    assert "external_ids" in tables
    assert "artwork" in tables
    assert "genres" in tables


# ── 18. initialize() runs full path from v0 to v3 ───────────────────────────

def test_initialize_from_empty_runs_full_path() -> None:
    connection = _fresh_connection()
    initialize(connection)

    version = _get_schema_version(connection)
    assert version == 4

    tables = _table_names(connection)
    assert "external_ids" in tables
    assert "genres" in tables
    assert "playback_history" in tables


# ── 19. initialize() is idempotent ───────────────────────────────────────────

def test_initialize_is_idempotent() -> None:
    connection = _fresh_connection()
    initialize(connection)
    initialize(connection)

    version = _get_schema_version(connection)
    assert version == 4

    assert connection.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 0


# ── 20. artwork requires provider ────────────────────────────────────────────

def test_artwork_rejects_null_provider() -> None:
    connection = _fresh_connection()
    initialize(connection)

    connection.execute("INSERT INTO movies(title) VALUES (?)", ("Test Movie",))
    movie_id = connection.execute("SELECT id FROM movies WHERE title = 'Test Movie'").fetchone()[0]

    try:
        connection.execute(
            "INSERT INTO artwork(entity_type, entity_id, artwork_type, provider_path) VALUES (?, ?, ?, ?)",
            ("movie", movie_id, "poster", "/path"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("NULL provider in artwork was not rejected")
