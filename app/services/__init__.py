from .playback import PlaybackService
from .favorites import FavoritesService
from .watchlist import WatchlistService
from .collections import CollectionsService
from .search import SearchService
from .statistics import StatisticsService
from .music import MusicService, MusicResolution
from .discovery import (
    DiscoveryService,
    LocalTrendingProvider,
    TrendingProvider,
    create_trending_provider,
)

__all__ = [
    "CollectionsService",
    "DiscoveryService",
    "FavoritesService",
    "LocalTrendingProvider",
    "MusicResolution",
    "MusicService",
    "PlaybackService",
    "SearchService",
    "StatisticsService",
    "TrendingProvider",
    "WatchlistService",
    "create_trending_provider",
]
