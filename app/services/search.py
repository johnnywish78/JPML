from __future__ import annotations

from app.library.search import SearchResult, SearchRepository


class SearchService:
    """UI-facing unified search API over SearchRepository.

    All SQL lives in the repository; this layer only combines results and
    applies deterministic ordering/capping.
    """

    def __init__(self, repository: SearchRepository) -> None:
        self._repo = repository

    @property
    def repository(self) -> SearchRepository:
        return self._repo

    def search_movies(self, query: str, limit: int = 50) -> list[SearchResult]:
        return self._repo.search_movies(query, limit=limit)

    def search_tv_shows(self, query: str, limit: int = 50) -> list[SearchResult]:
        return self._repo.search_tv_shows(query, limit=limit)

    def search_people(self, query: str, limit: int = 50) -> list[SearchResult]:
        return self._repo.search_people(query, limit=limit)

    def search_music(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Combined artist + album + track results, deterministically ordered."""
        combined = (
            self._repo.search_artists(query, limit=limit)
            + self._repo.search_albums(query, limit=limit)
            + self._repo.search_tracks(query, limit=limit)
        )
        combined.sort(key=lambda r: (r.title, r.entity_type, r.entity_id))
        return combined[:limit]

    def search_all(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Unified search across movies, TV shows, people, artists, albums
        and music tracks."""
        combined = (
            self._repo.search_movies(query, limit=limit)
            + self._repo.search_tv_shows(query, limit=limit)
            + self._repo.search_people(query, limit=limit)
            + self._repo.search_artists(query, limit=limit)
            + self._repo.search_albums(query, limit=limit)
            + self._repo.search_tracks(query, limit=limit)
        )
        combined.sort(key=lambda r: (r.title, r.entity_type, r.entity_id))
        return combined[:limit]
