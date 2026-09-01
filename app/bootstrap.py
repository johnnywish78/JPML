from __future__ import annotations

from app.database.connection import connect
from app.database.schema import initialize as initialize_schema
from app.library.playback_repository import PlaybackRepository
from app.player.controller import PlayerController
from app.player.events import PlaybackEventBus
from app.player.factory import create_backend
from app.services.playback import PlaybackService


def create_event_bus() -> PlaybackEventBus:
    return PlaybackEventBus()


def create_player_backend(
    name: str = "vlc",
    **kwargs: object,
) -> PlaybackService:  # type: ignore[override]
    """Create a player backend by name.

    .. deprecated:: Use :func:`create_backend` directly for backend creation.
    """
    return create_backend(name, **kwargs)  # type: ignore[return-value]


def create_playback_service(
    backend_name: str = "vlc",
    **kwargs: object,
) -> PlaybackService:
    from app.player import PlayerBackend

    backend: PlayerBackend = create_backend(backend_name, **kwargs)
    conn = connect()
    initialize_schema(conn)
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
