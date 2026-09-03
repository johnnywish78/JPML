from __future__ import annotations

import sqlite3

from app.database.connection import connect
from app.database.schema import initialize as initialize_schema
from app.library.playback_repository import PlaybackRepository
from app.player import PlayerBackend
from app.player.controller import PlayerController
from app.player.events import PlaybackEventBus
from app.player.factory import create_backend
from app.services.playback import PlaybackService


def _initialized_connection() -> sqlite3.Connection:
    connection = connect()
    initialize_schema(connection)
    return connection


def create_event_bus() -> PlaybackEventBus:
    return PlaybackEventBus()


def create_player_backend(
    name: str = "vlc",
    **kwargs: object,
) -> PlayerBackend:
    """Create a player backend by name.

    .. deprecated:: Use :func:`create_backend` directly for backend creation.
    """
    return create_backend(name, **kwargs)


def create_playback_service(
    backend_name: str = "vlc",
    **kwargs: object,
) -> PlaybackService:
    from app.player import PlayerBackend as Backend

    backend: Backend = create_backend(backend_name, **kwargs)
    conn = _initialized_connection()
    repo = PlaybackRepository(conn)
    return PlaybackService(backend, repo)


def create_player_controller(
    backend_name: str = "vlc",
    vlc_args: list[str] | None = None,
    mpv_args: list[str] | None = None,
    event_bus: PlaybackEventBus | None = None,
) -> PlayerController:
    return PlayerController(
        backend_name=backend_name,
        vlc_args=vlc_args,
        mpv_args=mpv_args,
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# Library / metadata / personal organization services
# ---------------------------------------------------------------------------


def create_favorites_service() -> "FavoritesService":
    from app.library.favorites_repository import FavoritesRepository
    from app.services.favorites import FavoritesService

    return FavoritesService(FavoritesRepository(_initialized_connection()))


def create_watchlist_service() -> "WatchlistService":
    from app.library.watchlist_repository import WatchlistRepository
    from app.services.watchlist import WatchlistService

    return WatchlistService(WatchlistRepository(_initialized_connection()))


def create_collections_service() -> "CollectionsService":
    from app.library.collections_repository import CollectionsRepository
    from app.services.collections import CollectionsService

    return CollectionsService(CollectionsRepository(_initialized_connection()))


def create_search_service() -> "SearchService":
    from app.library.search import SearchRepository
    from app.services.search import SearchService

    return SearchService(SearchRepository(_initialized_connection()))


def create_statistics_service() -> "StatisticsService":
    from app.library.statistics_repository import StatisticsRepository
    from app.services.statistics import StatisticsService

    return StatisticsService(StatisticsRepository(_initialized_connection()))


def create_music_service() -> "MusicService":
    from app.library.music_repository import MusicRepository
    from app.services.music import MusicService

    return MusicService(MusicRepository(_initialized_connection()))


def create_metadata_integration() -> "LibraryMetadataIntegration":
    """Composition of the metadata pipeline: provider registry (OMDb),
    metadata service and music service."""
    from app.config import load_config
    from app.metadata.library_integration import LibraryMetadataIntegration
    from app.metadata.omdb_provider import OMDbMetadataProvider
    from app.metadata.registry import MetadataProviderRegistry
    from app.metadata.repository import MetadataRepository
    from app.metadata.service import MetadataService
    from app.services.music import MusicService
    from app.library.music_repository import MusicRepository

    conn = _initialized_connection()
    config = load_config()

    registry = MetadataProviderRegistry()
    registry.register(OMDbMetadataProvider(config=config.omdb))

    metadata_service = MetadataService(
        MetadataRepository(conn),
        registry=registry,
    )
    music_service = MusicService(MusicRepository(conn))

    return LibraryMetadataIntegration(
        metadata_service, music_service=music_service
    )


def create_discovery_service(
    trending_provider: str | None = None,
) -> "DiscoveryService":
    from app.config import load_config
    from app.library.discovery_repository import DiscoveryRepository
    from app.services.discovery import (
        DiscoveryService,
        create_trending_provider,
    )

    conn = _initialized_connection()
    provider_name = trending_provider
    if provider_name is None:
        provider_name = load_config().discovery.trending_provider
    repository = DiscoveryRepository(conn)
    provider = create_trending_provider(provider_name, repository=repository)
    return DiscoveryService(repository, trending_provider=provider)
