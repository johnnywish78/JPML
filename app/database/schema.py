from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 6


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

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_items (
    id INTEGER PRIMARY KEY,
    collection_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, entity_type, entity_id),
    FOREIGN KEY(collection_id)
        REFERENCES collections(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    biography TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY,
    artist_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, title),
    FOREIGN KEY(artist_id)
        REFERENCES artists(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS music_tracks (
    id INTEGER PRIMARY KEY,
    album_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    track_number INTEGER,
    duration_seconds REAL,
    year INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(album_id, title),
    FOREIGN KEY(album_id)
        REFERENCES albums(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS track_files (
    track_id INTEGER NOT NULL,
    media_file_id INTEGER NOT NULL,
    PRIMARY KEY(track_id, media_file_id),
    FOREIGN KEY(track_id)
        REFERENCES music_tracks(id)
        ON DELETE CASCADE,
    FOREIGN KEY(media_file_id)
        REFERENCES media_files(id)
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
        version = 3

    if version < 4:
        _migrate_v3_to_v4(connection)
        version = 4

    if version < 5:
        _migrate_v4_to_v5(connection)
        version = 5

    if version < 6:
        _migrate_v5_to_v6(connection)


def _migrate_v4_to_v5(connection: sqlite3.Connection) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO schema_version(version) VALUES (5)"
    )
    connection.commit()


_V5_TO_V6_TABLES = """
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS collection_items (
    id INTEGER PRIMARY KEY,
    collection_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(collection_id, entity_type, entity_id),
    FOREIGN KEY(collection_id)
        REFERENCES collections(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    biography TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY,
    artist_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    year INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist_id, title),
    FOREIGN KEY(artist_id)
        REFERENCES artists(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS music_tracks (
    id INTEGER PRIMARY KEY,
    album_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    track_number INTEGER,
    duration_seconds REAL,
    year INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(album_id, title),
    FOREIGN KEY(album_id)
        REFERENCES albums(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS track_files (
    track_id INTEGER NOT NULL,
    media_file_id INTEGER NOT NULL,
    PRIMARY KEY(track_id, media_file_id),
    FOREIGN KEY(track_id)
        REFERENCES music_tracks(id)
        ON DELETE CASCADE,
    FOREIGN KEY(media_file_id)
        REFERENCES media_files(id)
        ON DELETE CASCADE
);
"""


def _migrate_v5_to_v6(connection: sqlite3.Connection) -> None:
    connection.executescript(_V5_TO_V6_TABLES)
    connection.execute(
        "INSERT OR REPLACE INTO schema_version(version) VALUES (6)"
    )
    connection.commit()


def _migrate_v3_to_v4(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS playback_history (
            id INTEGER PRIMARY KEY,
            media_type TEXT NOT NULL,
            media_id INTEGER NOT NULL,
            file_path TEXT NOT NULL DEFAULT '',
            started_at TEXT NOT NULL,
            stopped_at TEXT,
            last_position REAL DEFAULT 0.0,
            duration REAL DEFAULT 0.0,
            completed INTEGER DEFAULT 0,
            backend_used TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_playback_history_media
            ON playback_history(media_type, media_id);
        CREATE INDEX IF NOT EXISTS idx_playback_history_started
            ON playback_history(started_at);
        """
    )
    connection.execute(
        "INSERT OR REPLACE INTO schema_version(version) VALUES (4)"
    )
    connection.commit()
