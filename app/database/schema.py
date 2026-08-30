from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 3


SCHEMA = """
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

CREATE TABLE IF NOT EXISTS external_ids (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, provider),
    UNIQUE(provider, external_id)
);

CREATE TABLE IF NOT EXISTS artwork (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    artwork_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_path TEXT,
    local_path TEXT,
    width INTEGER,
    height INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, artwork_type, provider)
);

CREATE TABLE IF NOT EXISTS metadata_sources (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    provider TEXT NOT NULL,
    fetched_at TEXT,
    expires_at TEXT,
    metadata_version TEXT,
    user_override INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, provider)
);

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    PRIMARY KEY(movie_id, genre_id),
    FOREIGN KEY(movie_id)
        REFERENCES movies(id)
        ON DELETE CASCADE,
    FOREIGN KEY(genre_id)
        REFERENCES genres(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tv_genres (
    tv_show_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    PRIMARY KEY(tv_show_id, genre_id),
    FOREIGN KEY(tv_show_id)
        REFERENCES tv_shows(id)
        ON DELETE CASCADE,
    FOREIGN KEY(genre_id)
        REFERENCES genres(id)
        ON DELETE CASCADE
);
"""


def _get_schema_version(connection: sqlite3.Connection) -> int:
    try:
        row = connection.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS library_locations (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            label TEXT,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    try:
        connection.execute(
            "ALTER TABLE media_files ADD COLUMN is_missing INTEGER NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass
    connection.execute(
        "INSERT OR REPLACE INTO schema_version(version) VALUES (2)"
    )
    connection.commit()


def _migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS external_ids (
            id INTEGER PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            external_id TEXT NOT NULL,
            is_primary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(entity_type, entity_id, provider),
            UNIQUE(provider, external_id)
        );

        CREATE TABLE IF NOT EXISTS artwork (
            id INTEGER PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            artwork_type TEXT NOT NULL,
            provider TEXT NOT NULL,
            provider_path TEXT,
            local_path TEXT,
            width INTEGER,
            height INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(entity_type, entity_id, artwork_type, provider)
        );

        CREATE TABLE IF NOT EXISTS metadata_sources (
            id INTEGER PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            fetched_at TEXT,
            expires_at TEXT,
            metadata_version TEXT,
            user_override INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(entity_type, entity_id, provider)
        );

        CREATE TABLE IF NOT EXISTS genres (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS movie_genres (
            movie_id INTEGER NOT NULL,
            genre_id INTEGER NOT NULL,
            PRIMARY KEY(movie_id, genre_id),
            FOREIGN KEY(movie_id)
                REFERENCES movies(id)
                ON DELETE CASCADE,
            FOREIGN KEY(genre_id)
                REFERENCES genres(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tv_genres (
            tv_show_id INTEGER NOT NULL,
            genre_id INTEGER NOT NULL,
            PRIMARY KEY(tv_show_id, genre_id),
            FOREIGN KEY(tv_show_id)
                REFERENCES tv_shows(id)
                ON DELETE CASCADE,
            FOREIGN KEY(genre_id)
                REFERENCES genres(id)
                ON DELETE CASCADE
        );
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO schema_version(version) VALUES (3)"
    )
    connection.commit()


def initialize(connection: sqlite3.Connection) -> None:
    version = _get_schema_version(connection)

    if version < 1:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT OR IGNORE INTO schema_version(version) VALUES (1)"
        )
        connection.commit()
        version = 1

    if version < 2:
        _migrate_v1_to_v2(connection)
        version = 2

    if version < 3:
        _migrate_v2_to_v3(connection)
