from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.library.music_repository import MusicRepository


@dataclass(slots=True)
class SearchResult:
    entity_type: str
    entity_id: int
    title: str
    year: int | None = None
    overview: str | None = None
    match_score: float = 0.0


class SearchRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def search_movies(
        self, query: str, *, limit: int = 50
    ) -> list[SearchResult]:
        rows = self._conn.execute(
            """
            SELECT
                m.id,
                m.title,
                m.year,
                m.overview
            FROM movies AS m
            WHERE m.title LIKE ?
            ORDER BY
                CASE
                    WHEN m.title = ? THEN 0
                    WHEN m.title LIKE ? THEN 1
                    ELSE 2
                END,
                m.title
            LIMIT ?
            """,
            (f"%{query}%", query, f"{query}%", limit),
        ).fetchall()
        return [
            SearchResult(
                entity_type="movie",
                entity_id=row["id"],
                title=row["title"],
                year=row["year"],
                overview=row["overview"],
            )
            for row in rows
        ]

    def search_tv_shows(
        self, query: str, *, limit: int = 50
    ) -> list[SearchResult]:
        rows = self._conn.execute(
            """
            SELECT
                ts.id,
                ts.title,
                ts.year,
                ts.overview
            FROM tv_shows AS ts
            WHERE ts.title LIKE ?
            ORDER BY
                CASE
                    WHEN ts.title = ? THEN 0
                    WHEN ts.title LIKE ? THEN 1
                    ELSE 2
                END,
                ts.title
            LIMIT ?
            """,
            (f"%{query}%", query, f"{query}%", limit),
        ).fetchall()
        return [
            SearchResult(
                entity_type="tv_show",
                entity_id=row["id"],
                title=row["title"],
                year=row["year"],
                overview=row["overview"],
            )
            for row in rows
        ]

    def search_people(
        self, query: str, *, limit: int = 50
    ) -> list[SearchResult]:
        rows = self._conn.execute(
            """
            SELECT
                p.id,
                p.name,
                NULL AS year,
                p.biography AS overview
            FROM people AS p
            WHERE p.name LIKE ?
            ORDER BY
                CASE
                    WHEN p.name = ? THEN 0
                    WHEN p.name LIKE ? THEN 1
                    ELSE 2
                END,
                p.name
            LIMIT ?
            """,
            (f"%{query}%", query, f"{query}%", limit),
        ).fetchall()
        return [
            SearchResult(
                entity_type="person",
                entity_id=row["id"],
                title=row["name"],
                overview=row["overview"],
            )
            for row in rows
        ]

    def search_artists(
        self, query: str, *, limit: int = 50
    ) -> list[SearchResult]:
        artists = MusicRepository(self._conn).search_artists(query, limit=limit)
        return [
            SearchResult(
                entity_type="artist",
                entity_id=a.id,
                title=a.name,
                overview=a.biography,
            )
            for a in artists
        ]

    def search_albums(
        self, query: str, *, limit: int = 50
    ) -> list[SearchResult]:
        albums = MusicRepository(self._conn).search_albums(query, limit=limit)
        return [
            SearchResult(
                entity_type="album",
                entity_id=a.id,
                title=a.title,
                year=a.year,
                overview=a.artist.name if a.artist is not None else None,
            )
            for a in albums
        ]

    def search_tracks(
        self, query: str, *, limit: int = 50
    ) -> list[SearchResult]:
        tracks = MusicRepository(self._conn).search_tracks(query, limit=limit)
        return [
            SearchResult(
                entity_type="track",
                entity_id=t.id,
                title=t.title,
                year=t.year,
                overview=t.artist.name if t.artist is not None else None,
            )
            for t in tracks
        ]

    def search_all(
        self, query: str, *, limit: int = 50
    ) -> list[SearchResult]:
        movies = self.search_movies(query, limit=limit)
        tv = self.search_tv_shows(query, limit=limit)
        combined = movies + tv
        combined.sort(key=lambda r: (r.match_score, r.title))
        return combined[:limit]
