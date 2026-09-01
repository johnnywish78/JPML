from __future__ import annotations

from app.database.connection import connect
from app.database.schema import initialize as initialize_schema
from app.library.playback_repository import PlaybackRepository
from app.player.controller import PlayerController
from app.player.events import PlaybackEventBus
from app.player.vlc_backend import VLCPlayerBackend
from app.services.playback import PlaybackService


def create_event_bus() -> PlaybackEventBus:
    return PlaybackEventBus()


def create_vlc_backend(
    vlc_args: list[str] | None = None,
) -> VLCPlayerBackend:
    return VLCPlayerBackend(vlc_args=vlc_args or ["--quiet"])


def create_playback_service(
    backend: VLCPlayerBackend | None = None,
) -> PlaybackService:
    if backend is None:
        backend = create_vlc_backend()
    conn = connect()
    initialize_schema(conn)
    repo = PlaybackRepository(conn)
    return PlaybackService(backend, repo)


def create_player_controller(
    vlc_args: list[str] | None = None,
    event_bus: PlaybackEventBus | None = None,
) -> PlayerController:
    return PlayerController(vlc_args=vlc_args, event_bus=event_bus)
