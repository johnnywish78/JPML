from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


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

    def search_all(
        self, query: str, *, limit: int = 50
    ) -> list[SearchResult]:
        movies = self.search_movies(query, limit=limit)
        tv = self.search_tv_shows(query, limit=limit)
        combined = movies + tv
        combined.sort(key=lambda r: (r.match_score, r.title))
        return combined[:limit]
