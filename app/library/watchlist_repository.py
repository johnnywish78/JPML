from __future__ import annotations

from app.library.favorites_repository import FavoriteEntry, FavoritesRepository

WatchlistEntry = FavoriteEntry


class WatchlistRepository(FavoritesRepository):
    """Persistence for watchlist entries (same semantics as favorites)."""

    TABLE = "watchlist"

    def is_in_watchlist(self, entity_type: str, entity_id: int) -> bool:
        return self.is_favorite(entity_type, entity_id)
