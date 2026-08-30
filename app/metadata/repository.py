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
