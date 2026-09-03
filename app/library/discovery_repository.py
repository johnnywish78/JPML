from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrendingItem:
    entity_type: str
    entity_id: int
    title: str
    plays: int
    reason: str


@dataclass(frozen=True, slots=True)
class Recommendation:
    entity_type: str
    entity_id: int
    title: str
    year: int | None
    score: int
    reason: str


class DiscoveryRepository:
    """Queries backing trending and recommendation features.

    The default trending strategy is local and deterministic: media with the
    most playback activity inside a recent window, falling back to the most
    recently added library entries when no recent activity exists. No
    external popularity data is fabricated.
    """

    TRENDING_WINDOW_DAYS = 14

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_trending_recent(self, limit: int) -> list[TrendingItem]:
        rows = self._conn.execute(
            """
            SELECT
                ph.media_type AS entity_type,
                ph.media_id AS entity_id,
                COALESCE(m.title, s.title, e.title, 'Unknown') AS title,
                COUNT(*) AS plays
            FROM playback_history AS ph
            LEFT JOIN movies AS m ON ph.media_type = 'movie' AND m.id = ph.media_id
            LEFT JOIN tv_shows AS s ON ph.media_type = 'tv' AND s.id = ph.media_id
            LEFT JOIN episodes AS e ON ph.media_type = 'episode' AND e.id = ph.media_id
            WHERE ph.started_at >= datetime('now', ?)
            GROUP BY ph.media_type, ph.media_id
            ORDER BY plays DESC,
                     MAX(COALESCE(ph.stopped_at, ph.started_at)) DESC,
                     ph.media_type, ph.media_id
            LIMIT ?
            """,
            (f"-{self.TRENDING_WINDOW_DAYS} days", limit),
        ).fetchall()
        return [
            TrendingItem(
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                title=row["title"],
                plays=int(row["plays"]),
                reason=f"played {int(row['plays'])} time(s) in the last "
                f"{self.TRENDING_WINDOW_DAYS} days",
            )
            for row in rows
        ]

    def get_newest_added(self, limit: int) -> list[TrendingItem]:
        movies = self._conn.execute(
            "SELECT id, title FROM movies "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        shows = self._conn.execute(
            "SELECT id, title FROM tv_shows "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        combined: list[TrendingItem] = []
        for row in movies:
            combined.append(
                TrendingItem(
                    entity_type="movie",
                    entity_id=row["id"],
                    title=row["title"],
                    plays=0,
                    reason="recently added to the library",
                )
            )
        for row in shows:
            combined.append(
                TrendingItem(
                    entity_type="tv",
                    entity_id=row["id"],
                    title=row["title"],
                    plays=0,
                    reason="recently added to the library",
                )
            )
        combined.sort(key=lambda t: (t.entity_type, -t.entity_id))
        return combined[:limit]

    # -- recommendations -----------------------------------------------------

    def _reference_genres(self, entity_type: str, entity_id: int) -> list[int]:
        table = "movie_genres" if entity_type == "movie" else "tv_genres"
        column = "movie_id" if entity_type == "movie" else "tv_show_id"
        rows = self._conn.execute(
            f"SELECT genre_id FROM {table} WHERE {column} = ?", (entity_id,)
        ).fetchall()
        return [int(row[0]) for row in rows]

    def genre_recommendations(
        self, entity_type: str, entity_id: int, limit: int
    ) -> list[Recommendation]:
        if entity_type not in ("movie", "tv"):
            raise ValueError(
                f"Recommendations are only supported for movie/tv, got {entity_type!r}"
            )
        ref_genres = self._reference_genres(entity_type, entity_id)
        if not ref_genres:
            return []

        table = "movies" if entity_type == "movie" else "tv_shows"
        link_table = "movie_genres" if entity_type == "movie" else "tv_genres"
        link_column = "movie_id" if entity_type == "movie" else "tv_show_id"
        placeholders = ", ".join("?" for _ in ref_genres)

        rows = self._conn.execute(
            f"""
            SELECT
                t.id AS entity_id,
                t.title AS title,
                t.year AS year,
                COUNT(DISTINCT lg.genre_id) AS shared
            FROM {table} AS t
            JOIN {link_table} AS lg ON lg.{link_column} = t.id
            WHERE t.id != ? AND lg.genre_id IN ({placeholders})
            GROUP BY t.id
            ORDER BY shared DESC, t.title, t.id
            LIMIT ?
            """,
            [entity_id, *ref_genres, limit],
        ).fetchall()

        fav_rows = self._conn.execute(
            "SELECT entity_id FROM favorites WHERE entity_type = ?", (entity_type,)
        ).fetchall()
        favorite_ids = {int(row[0]) for row in fav_rows}

        results: list[Recommendation] = []
        for row in rows:
            shared = int(row["shared"])
            is_favorite = row["entity_id"] in favorite_ids
            score = shared + (1 if is_favorite else 0)
            reason = f"shares {shared} genre(s) with your item"
            if is_favorite:
                reason += " and is in your favorites"
            results.append(
                Recommendation(
                    entity_type=entity_type,
                    entity_id=int(row["entity_id"]),
                    title=row["title"],
                    year=row["year"],
                    score=score,
                    reason=reason,
                )
            )
        results.sort(key=lambda r: (-r.score, r.title, r.entity_id))
        return results[:limit]

    def unwatched_recent(
        self, entity_type: str, limit: int, exclude_id: int | None = None
    ) -> list[Recommendation]:
        """Fallback: recent library items not yet started in playback history."""
        if entity_type not in ("movie", "tv"):
            raise ValueError(
                f"Recommendations are only supported for movie/tv, got {entity_type!r}"
            )
        table = "movies" if entity_type == "movie" else "tv_shows"
        rows = self._conn.execute(
            f"""
            SELECT t.id AS entity_id, t.title AS title, t.year AS year
            FROM {table} AS t
            WHERE NOT EXISTS (
                SELECT 1 FROM playback_history AS ph
                WHERE ph.media_type = ? AND ph.media_id = t.id
            )
              AND (t.id != ? OR ? IS NULL)
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT ?
            """,
            (entity_type, exclude_id, exclude_id, limit),
        ).fetchall()
        return [
            Recommendation(
                entity_type=entity_type,
                entity_id=int(row["entity_id"]),
                title=row["title"],
                year=row["year"],
                score=0,
                reason="recently added and not watched yet",
            )
            for row in rows
        ]
