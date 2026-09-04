"""Central composition of JPML backend services for the UI.

The UI never instantates backend services on its own — every screen
receives a UiContext built from this composition. All service
construction goes through the existing app.bootstrap factories.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.bootstrap import (
    create_collections_service,
    create_discovery_service,
    create_event_bus,
    create_favorites_service,
    create_music_service,
    create_player_controller,
    create_search_service,
    create_statistics_service,
    create_watchlist_service,
)
from app.library.discovery_repository import DiscoveryRepository
from app.library.media_repository import MediaRepository
from app.library.library_repository import LibraryRepository
from app.library.music_repository import MusicRepository
from app.library.playback_repository import PlaybackRepository
from app.metadata.repository import MetadataRepository
from app.player.controller import PlayerController
from app.player.events import PlaybackEventBus

from ui.app.navigation import Navigation


@dataclass(slots=True)
class ServiceComposition:
    """Holds every backend service the UI may consume."""

    favorites: object
    watchlist: object
    collections: object
    search: object
    statistics: object
    music: object
    discovery: object
    media_repository: MediaRepository
    library_repository: LibraryRepository
    metadata_repository: MetadataRepository
    playback_repository: PlaybackRepository
    discovery_repository: DiscoveryRepository
    music_repository: MusicRepository
    event_bus: PlaybackEventBus
    player: PlayerController | None = None
    # extra context for the UI (e.g., whether a real backend is available)
    extras: dict = field(default_factory=dict)


def build_services() -> ServiceComposition:
    """Construct the full service graph via app.bootstrap factories."""
    from app.bootstrap import _initialized_connection  # noqa: PLC2701

    conn = _initialized_connection()

    event_bus = create_event_bus()

    composition = ServiceComposition(
        favorites=create_favorites_service(),
        watchlist=create_watchlist_service(),
        collections=create_collections_service(),
        search=create_search_service(),
        statistics=create_statistics_service(),
        music=create_music_service(),
        discovery=create_discovery_service(),
        media_repository=MediaRepository(conn),
        library_repository=LibraryRepository(conn),
        metadata_repository=MetadataRepository(conn),
        playback_repository=PlaybackRepository(conn),
        discovery_repository=DiscoveryRepository(conn),
        music_repository=MusicRepository(conn),
        event_bus=event_bus,
    )
    # The player controller is deliberately created lazily (see
    # MainWindow/PlayerScreen) so the app can start without any
    # playback engine being required at composition time.
    return composition


def create_ui_navigation(initial: str = "home") -> Navigation:
    return Navigation(initial=initial)


def _conn_of(obj):
    return getattr(obj, "_conn", None) or getattr(obj, "connection", None)


def _close(conn) -> None:
    if conn is not None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 — best effort on teardown
            pass


def close_services(composition: ServiceComposition) -> None:
    """Close every backend connection owned by a composition.

    Called by background loader threads after a read completes so the
    thread-bound SQLite connections (frozen backend) do not leak. This
    only closes connections; it never modifies schema or state.

    Each frozen service factory opens its own connection (bootstrap
    pattern), so we close the standalone repositories and the repository
    behind each service.
    """
    repos = (
        composition.media_repository,
        composition.library_repository,
        composition.metadata_repository,
        composition.playback_repository,
        composition.discovery_repository,
        composition.music_repository,
    )
    for repo in repos:
        _close(_conn_of(repo))
    for service in (
        composition.favorites,
        composition.watchlist,
        composition.collections,
        composition.search,
        composition.statistics,
        composition.music,
        composition.discovery,
    ):
        _close(_conn_of(getattr(service, "repository", None)))
