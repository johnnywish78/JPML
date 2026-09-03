from __future__ import annotations

from abc import ABC, abstractmethod

from app.library.discovery_repository import (
    DiscoveryRepository,
    Recommendation,
    TrendingItem,
)


class TrendingProvider(ABC):
    """Abstraction for trending data sources.

    The default, local provider derives trending deterministically from
    playback activity and library recency. An external provider can be
    substituted later without changing DiscoveryService or the UI-facing API.
    """

    name: str = "abstract"

    @abstractmethod
    def get_trending(self, limit: int = 10) -> list[TrendingItem]:
        """Return up to *limit* trending items, most relevant first."""


class LocalTrendingProvider(TrendingProvider):
    """Deterministic, local trending: most replayed items in a recent
    window, falling back to most recently added library entries."""

    name = "local"

    def __init__(self, repository: DiscoveryRepository) -> None:
        self._repo = repository

    def get_trending(self, limit: int = 10) -> list[TrendingItem]:
        items = self._repo.get_trending_recent(limit)
        if items:
            return items
        return self._repo.get_newest_added(limit)


def create_trending_provider(
    name: str | None = None,
    repository: DiscoveryRepository | None = None,
) -> TrendingProvider:
    name = (name or "local").strip().lower()
    if name == "local":
        if repository is None:
            raise ValueError("local trending provider requires a DiscoveryRepository")
        return LocalTrendingProvider(repository)
    raise ValueError(
        f"Unknown trending provider {name!r}. Supported: 'local'"
    )


class DiscoveryService:
    """UI-facing discovery API: trending + recommendations.

    Recommendations use a deterministic genre-overlap strategy over the
    local library (with a favorites boost), falling back to recent
    unwatched items. No external calls are made by the default wiring.
    """

    def __init__(
        self,
        repository: DiscoveryRepository,
        trending_provider: TrendingProvider | None = None,
    ) -> None:
        self._repo = repository
        self._trending = trending_provider or LocalTrendingProvider(repository)

    @property
    def trending_provider(self) -> TrendingProvider:
        return self._trending

    def trending(self, limit: int = 10) -> list[TrendingItem]:
        return self._trending.get_trending(limit)

    def recommendations(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 10,
    ) -> list[Recommendation]:
        results = self._repo.genre_recommendations(entity_type, entity_id, limit)
        if results:
            return results
        return self._repo.unwatched_recent(entity_type, limit, exclude_id=entity_id)

    def discover(self, limit: int = 10) -> list[TrendingItem]:
        """General 'what to look at' feed: the current trending list."""
        return self._trending.get_trending(limit)
