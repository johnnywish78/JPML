from __future__ import annotations

import sqlite3
from typing import Any


class MetadataRepository:
    """Persistence layer for provider metadata and artwork."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_external_id(
        self,
        entity_type: str,
        entity_id: int,
        provider: str,
        external_id: str,
        *,
        is_primary: bool = False,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO external_ids
                (entity_type, entity_id, provider, external_id, is_primary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                provider,
                external_id,
                int(is_primary),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def get_external_id(
        self,
        entity_type: str,
        entity_id: int,
        provider: str,
    ) -> str | None:
        row = self.connection.execute(
            """
            SELECT external_id
            FROM external_ids
            WHERE entity_type = ?
              AND entity_id = ?
              AND provider = ?
            """,
            (entity_type, entity_id, provider),
        ).fetchone()

        return None if row is None else str(row[0])

    def list_external_ids(
        self,
        entity_type: str,
        entity_id: int,
    ) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT provider, external_id, is_primary
            FROM external_ids
            WHERE entity_type = ?
              AND entity_id = ?
            ORDER BY provider
            """,
            (entity_type, entity_id),
        ).fetchall()

        return [
            {
                "provider": str(row[0]),
                "external_id": str(row[1]),
                "is_primary": bool(row[2]),
            }
            for row in rows
        ]

    def upsert_external_id(
        self,
        entity_type: str,
        entity_id: int,
        provider: str,
        external_id: str,
        *,
        is_primary: bool = False,
    ) -> int:
        existing = self.connection.execute(
            """
            SELECT id
            FROM external_ids
            WHERE entity_type = ?
              AND entity_id = ?
              AND provider = ?
            """,
            (entity_type, entity_id, provider),
        ).fetchone()

        if existing is None:
            return self.add_external_id(
                entity_type,
                entity_id,
                provider,
                external_id,
                is_primary=is_primary,
            )

        self.connection.execute(
            """
            UPDATE external_ids
            SET external_id = ?, is_primary = ?
            WHERE id = ?
            """,
            (external_id, int(is_primary), existing[0]),
        )
        self.connection.commit()
        return int(existing[0])

    def add_artwork(
        self,
        entity_type: str,
        entity_id: int,
        artwork_type: str,
        *,
        provider: str | None = None,
        provider_path: str | None = None,
        local_path: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO artwork
                (
                    entity_type,
                    entity_id,
                    artwork_type,
                    provider,
                    provider_path,
                    local_path,
                    width,
                    height
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                artwork_type,
                provider,
                provider_path,
                local_path,
                width,
                height,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def list_artwork(
        self,
        entity_type: str,
        entity_id: int,
    ) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT
                artwork_type,
                provider,
                provider_path,
                local_path,
                width,
                height
            FROM artwork
            WHERE entity_type = ?
              AND entity_id = ?
            ORDER BY artwork_type, provider
            """,
            (entity_type, entity_id),
        ).fetchall()

        return [
            {
                "artwork_type": str(row[0]),
                "provider": row[1],
                "provider_path": row[2],
                "local_path": row[3],
                "width": row[4],
                "height": row[5],
            }
            for row in rows
        ]

    def add_metadata_source(
        self,
        entity_type: str,
        entity_id: int,
        provider: str,
        *,
        fetched_at: str | None = None,
        expires_at: str | None = None,
        metadata_version: str | None = None,
        user_override: bool = False,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO metadata_sources
                (
                    entity_type,
                    entity_id,
                    provider,
                    fetched_at,
                    expires_at,
                    metadata_version,
                    user_override
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_id,
                provider,
                fetched_at,
                expires_at,
                metadata_version,
                int(user_override),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def get_metadata_source(
        self,
        entity_type: str,
        entity_id: int,
        provider: str,
    ) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT
                provider,
                fetched_at,
                expires_at,
                metadata_version,
                user_override
            FROM metadata_sources
            WHERE entity_type = ?
              AND entity_id = ?
              AND provider = ?
            """,
            (entity_type, entity_id, provider),
        ).fetchone()

        if row is None:
            return None

        return {
            "provider": str(row[0]),
            "fetched_at": row[1],
            "expires_at": row[2],
            "metadata_version": row[3],
            "user_override": bool(row[4]),
        }

    def upsert_metadata_source(
        self,
        entity_type: str,
        entity_id: int,
        provider: str,
        *,
        fetched_at: str | None = None,
        expires_at: str | None = None,
        metadata_version: str | None = None,
        user_override: bool = False,
    ) -> int:
        existing = self.connection.execute(
            """
            SELECT id
            FROM metadata_sources
            WHERE entity_type = ?
              AND entity_id = ?
              AND provider = ?
            """,
            (entity_type, entity_id, provider),
        ).fetchone()

        if existing is None:
            return self.add_metadata_source(
                entity_type,
                entity_id,
                provider,
                fetched_at=fetched_at,
                expires_at=expires_at,
                metadata_version=metadata_version,
                user_override=user_override,
            )

        self.connection.execute(
            """
            UPDATE metadata_sources
            SET
                fetched_at = ?,
                expires_at = ?,
                metadata_version = ?,
                user_override = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                fetched_at,
                expires_at,
                metadata_version,
                int(user_override),
                existing[0],
            ),
        )
        self.connection.commit()
        return int(existing[0])

    def get_or_create_genre(self, name: str) -> int:
        normalized = name.strip()
        if not normalized:
            raise ValueError("genre name must not be empty")

        row = self.connection.execute(
            "SELECT id FROM genres WHERE name = ?",
            (normalized,),
        ).fetchone()

        if row is not None:
            return int(row[0])

        cursor = self.connection.execute(
            "INSERT INTO genres(name) VALUES (?)",
            (normalized,),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def set_movie_genres(
        self,
        movie_id: int,
        genres: list[str],
    ) -> None:
        self.connection.execute(
            "DELETE FROM movie_genres WHERE movie_id = ?",
            (movie_id,),
        )

        for name in dict.fromkeys(g.strip() for g in genres if g.strip()):
            genre_id = self.get_or_create_genre(name)
            self.connection.execute(
                """
                INSERT OR IGNORE INTO movie_genres(movie_id, genre_id)
                VALUES (?, ?)
                """,
                (movie_id, genre_id),
            )

        self.connection.commit()

    def set_tv_genres(
        self,
        tv_show_id: int,
        genres: list[str],
    ) -> None:
        self.connection.execute(
            "DELETE FROM tv_genres WHERE tv_show_id = ?",
            (tv_show_id,),
        )

        for name in dict.fromkeys(g.strip() for g in genres if g.strip()):
            genre_id = self.get_or_create_genre(name)
            self.connection.execute(
                """
                INSERT OR IGNORE INTO tv_genres(tv_show_id, genre_id)
                VALUES (?, ?)
                """,
                (tv_show_id, genre_id),
            )

        self.connection.commit()

    def get_movie_genres(self, movie_id: int) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT g.name
            FROM genres AS g
            JOIN movie_genres AS mg ON mg.genre_id = g.id
            WHERE mg.movie_id = ?
            ORDER BY g.name
            """,
            (movie_id,),
        ).fetchall()

        return [str(row[0]) for row in rows]

    def get_tv_genres(self, tv_show_id: int) -> list[str]:
        rows = self.connection.execute(
            """
            SELECT g.name
            FROM genres AS g
            JOIN tv_genres AS tg ON tg.genre_id = g.id
            WHERE tg.tv_show_id = ?
            ORDER BY g.name
            """,
            (tv_show_id,),
        ).fetchall()

        return [str(row[0]) for row in rows]


    def find_movie_by_title(
        self,
        *,
        title: str,
        year: int | None = None,
    ) -> int | None:
        """Return an existing movie id when title matches (and year when
        provided), otherwise None."""
        if year is not None:
            row = self.connection.execute(
                "SELECT id FROM movies WHERE title = ? AND year = ?",
                (title, year),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT id FROM movies WHERE title = ?",
                (title,),
            ).fetchone()
        return int(row["id"]) if row is not None else None

    def find_tv_show_by_title(
        self,
        *,
        title: str,
        year: int | None = None,
    ) -> int | None:
        """Return an existing tv_show id when title matches (and year when
        provided), otherwise None."""
        if year is not None:
            row = self.connection.execute(
                "SELECT id FROM tv_shows WHERE title = ? AND year = ?",
                (title, year),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT id FROM tv_shows WHERE title = ?",
                (title,),
            ).fetchone()
        return int(row["id"]) if row is not None else None

    def create_movie(self, *, title: str, year: int | None = None) -> int:
        cursor = self.connection.execute(
            "INSERT INTO movies(title, year) VALUES (?, ?)",
            (title, year),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def create_tv_show(self, *, title: str, year: int | None = None) -> int:
        cursor = self.connection.execute(
            "INSERT INTO tv_shows(title, year) VALUES (?, ?)",
            (title, year),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def find_by_external_id(
        self,
        *,
        entity_type: str,
        provider: str,
        external_id: str,
    ) -> int | None:
        row = self.connection.execute(
            """
            SELECT entity_id
            FROM external_ids
            WHERE entity_type = ?
              AND provider = ?
              AND external_id = ?
            """,
            (entity_type, provider, external_id),
        ).fetchone()

        return int(row["entity_id"]) if row is not None else None

    def set_external_id(
        self,
        *,
        entity_type: str,
        entity_id: int,
        provider: str,
        external_id: str,
        is_primary: bool = False,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO external_ids(
                entity_type,
                entity_id,
                provider,
                external_id,
                is_primary
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(entity_type, entity_id, provider)
            DO UPDATE SET
                external_id = excluded.external_id,
                is_primary = excluded.is_primary
            """,
            (
                entity_type,
                entity_id,
                provider,
                external_id,
                int(is_primary),
            ),
        )
        self.connection.commit()

    def update_entity_metadata(
        self,
        *,
        entity_type: str,
        entity_id: int,
        title: str | None = None,
        year: int | None = None,
        overview: str | None = None,
        tmdb_id: int | None = None,
        imdb_id: str | None = None,
    ) -> None:
        table = {
            "movie": "movies",
            "tv": "tv_shows",
        }.get(entity_type)

        if table is None:
            raise ValueError(f"Unsupported entity type: {entity_type}")

        sets: list[str] = []
        params: list[Any] = []
        if title is not None:
            sets.append("title = COALESCE(?, title)")
            params.append(title)
        if year is not None:
            sets.append("year = COALESCE(?, year)")
            params.append(year)
        if overview is not None:
            sets.append("overview = COALESCE(?, overview)")
            params.append(overview)
        if tmdb_id is not None:
            sets.append("tmdb_id = COALESCE(?, tmdb_id)")
            params.append(tmdb_id)
        if imdb_id is not None:
            sets.append("imdb_id = COALESCE(?, imdb_id)")
            params.append(imdb_id)
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(entity_id)

        self.connection.execute(
            f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        self.connection.commit()

    def record_metadata_source(
        self,
        *,
        entity_type: str,
        entity_id: int,
        provider: str,
        metadata_version: str | None = None,
        user_override: bool = False,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO metadata_sources(
                entity_type,
                entity_id,
                provider,
                fetched_at,
                metadata_version,
                user_override
            )
            VALUES (
                ?, ?, ?, CURRENT_TIMESTAMP, ?, ?
            )
            ON CONFLICT(entity_type, entity_id, provider)
            DO UPDATE SET
                fetched_at = CURRENT_TIMESTAMP,
                metadata_version = excluded.metadata_version,
                user_override = excluded.user_override,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                entity_type,
                entity_id,
                provider,
                metadata_version,
                int(user_override),
            ),
        )
        self.connection.commit()

    # ------------------------------------------------------------------ #
    # People / cast
    # ------------------------------------------------------------------ #

    def upsert_person(
        self,
        *,
        name: str,
        tmdb_id: int | None = None,
        imdb_id: str | None = None,
        biography: str | None = None,
    ) -> int:
        """Insert or return existing person by tmdb_id / imdb_id / name."""
        if tmdb_id is not None:
            row = self.connection.execute(
                "SELECT id FROM people WHERE tmdb_id = ?", (tmdb_id,)
            ).fetchone()
            if row is not None:
                return int(row["id"])
        if imdb_id is not None:
            row = self.connection.execute(
                "SELECT id FROM people WHERE imdb_id = ?", (imdb_id,)
            ).fetchone()
            if row is not None:
                return int(row["id"])
        # Fall back to name-based dedup
        row = self.connection.execute(
            "SELECT id FROM people WHERE name = ?", (name,)
        ).fetchone()
        if row is not None:
            return int(row["id"])

        cursor = self.connection.execute(
            """
            INSERT INTO people (name, tmdb_id, imdb_id, biography)
            VALUES (?, ?, ?, ?)
            """,
            (name, tmdb_id, imdb_id, biography),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def add_person_relationship(
        self,
        *,
        entity_type: str,
        entity_id: int,
        person_id: int,
        character: str | None = None,
        role: str | None = None,
    ) -> None:
        table = {
            "movie": "movie_people",
            "tv": "tv_people",
        }.get(entity_type)
        if table is None:
            return

        id_col = "movie_id" if table == "movie_people" else "tv_show_id"
        # Only include character/role if the table has those columns
        col_names = [c[0] for c in self.connection.execute(f"PRAGMA table_info({table})").fetchall()]
        cols = [id_col, "person_id"]
        vals = [entity_id, person_id]
        if "character_name" in col_names:
            cols.append("character_name")
            vals.append(character)
        if "role" in col_names:
            cols.append("role")
            vals.append(role)
        placeholders = ", ".join("?" * len(cols))
        self.connection.execute(
            f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )
        self.connection.commit()

    # ------------------------------------------------------------------ #
    # Artwork upsert
    # ------------------------------------------------------------------ #

    def upsert_artwork(
        self,
        *,
        entity_type: str,
        entity_id: int,
        artwork_type: str,
        provider: str,
        local_path: str | None = None,
        provider_path: str | None = None,
    ) -> None:
        """Insert or update an artwork row. Idempotent per (entity_type,
        entity_id, artwork_type, provider)."""
        existing = self.connection.execute(
            """
            SELECT id FROM artwork
            WHERE entity_type = ? AND entity_id = ?
              AND artwork_type = ? AND provider = ?
            """,
            (entity_type, entity_id, artwork_type, provider),
        ).fetchone()

        if existing is None:
            self.connection.execute(
                """
                INSERT INTO artwork
                    (entity_type, entity_id, artwork_type, provider,
                     provider_path, local_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (entity_type, entity_id, artwork_type, provider,
                 provider_path, local_path),
            )
        else:
            self.connection.execute(
                """
                UPDATE artwork SET
                    provider_path = COALESCE(?, provider_path),
                    local_path = COALESCE(?, local_path),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (provider_path, local_path, existing["id"]),
            )
        self.connection.commit()

    def list_people_by_entity(
        self,
        entity_type: str,
        entity_id: int,
    ) -> list[dict[str, Any]]:
        """Return people associated with a movie or TV show, including
        character/role information and person artwork."""
        table = {
            "movie": "movie_people",
            "tv": "tv_people",
        }.get(entity_type)
        if table is None:
            return []

        id_col = "movie_id" if table == "movie_people" else "tv_show_id"
        col_names = [c[0] for c in self.connection.execute(f"PRAGMA table_info({table})").fetchall()]
        char_col = "character_name" if "character_name" in col_names else ("character" if "character" in col_names else None)

        select_parts = ["p.id", "p.name", "p.biography", "p.tmdb_id"]
        if char_col:
            select_parts.append(f"mp.{char_col} AS character")
        if "role" in col_names:
            select_parts.append("mp.role")
        order_clause = ""
        if "order" in col_names:
            order_clause = 'ORDER BY CASE WHEN mp."order" IS NOT NULL THEN CAST(mp."order" AS INTEGER) ELSE 9999 END, p.name'
        else:
            order_clause = "ORDER BY p.name"

        rows = self.connection.execute(
            f"""
            SELECT {", ".join(select_parts)}
            FROM {table} mp
            JOIN people p ON p.id = mp.person_id
            WHERE mp.{id_col} = ?
            {order_clause}
            """,
            (entity_id,),
        ).fetchall()

        result = []
        for row in rows:
            person_artwork = self.list_artwork("person", row["id"])
            d: dict[str, Any] = {
                "id": row["id"],
                "name": row["name"],
                "biography": row["biography"],
                "tmdb_id": row["tmdb_id"],
            }
            if char_col:
                d["character"] = row["character"]
            if "role" in col_names:
                d["role"] = row["role"]
            d["artwork"] = person_artwork[0] if person_artwork else None
            result.append(d)
        return result

    def list_seasons(
        self,
        tv_show_id: int,
    ) -> list[dict[str, Any]]:
        """Return seasons for a TV show."""
        rows = self.connection.execute(
            "SELECT id, tv_show_id, season_number FROM seasons WHERE tv_show_id = ? ORDER BY season_number",
            (tv_show_id,),
        ).fetchall()
        return [
            {"id": r["id"], "tv_show_id": r["tv_show_id"], "season_number": r["season_number"]}
            for r in rows
        ]

    def list_episodes(
        self,
        season_id: int,
    ) -> list[dict[str, Any]]:
        """Return episodes for a season."""
        rows = self.connection.execute(
            "SELECT id, season_id, episode_number, title, overview, air_date FROM episodes WHERE season_id = ? ORDER BY episode_number",
            (season_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "season_id": r["season_id"],
                "episode_number": r["episode_number"],
                "title": r["title"],
                "overview": r["overview"],
                "air_date": r["air_date"],
            }
            for r in rows
        ]
