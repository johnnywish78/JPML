from __future__ import annotations

import logging
import os
import threading
from typing import Any

from app.library.playback_repository import PlaybackRepository
from app.player import (
    AudioTrack,
    MediaInfo,
    PlaybackCallbacks,
    PlayerBackend,
    SubtitleTrack,
    VideoTrack,
)
from app.player.events import PlaybackEvent, PlaybackEventData, PlaybackEventBus
from app.services.playback import PlaybackService

log = logging.getLogger(__name__)


class PlayerController:
    """High-level player controller that bridges a PlayerBackend and
    PlaybackService with an application-level event system.

    This is the primary integration point between the playback engine
    and the future UI layer.  It owns the backend lifecycle, wires
    callbacks, and exposes a clean API without leaking backend objects.

    Thread safety:
      All public methods are safe to call from any thread.
      Event callbacks are dispatched synchronously on the calling thread.
    """

    def __init__(
        self,
        *,
        backend_name: str = "vlc",
        vlc_args: list[str] | None = None,
        mpv_args: list[str] | None = None,
        event_bus: PlaybackEventBus | None = None,
    ) -> None:
        self._event_bus = event_bus or PlaybackEventBus()
        self._lock = threading.Lock()

        from app.player.factory import create_backend

        self._backend = create_backend(
            backend_name,
            callbacks=PlaybackCallbacks(
                on_end_reached=self._on_backend_end_reached,
                on_error=self._on_backend_error,
                on_state_changed=self._on_backend_state_changed,
            ),
            vlc_args=vlc_args,
            mpv_args=mpv_args,
        )
        self._backend_name = backend_name

        from app.database.connection import connect
        from app.database.schema import initialize as initialize_schema

        self._conn = connect()
        initialize_schema(self._conn)
        self._repo = PlaybackRepository(self._conn)
        self._service = PlaybackService(self._backend, self._repo)

        self._current_media_type: str | None = None
        self._current_media_id: int | None = None

    @property
    def event_bus(self) -> PlaybackEventBus:
        return self._event_bus

    @property
    def service(self) -> PlaybackService:
        return self._service

    @property
    def backend(self) -> PlayerBackend:
        return self._backend

    # -- core playback -------------------------------------------------------

    def open(
        self,
        media_type: str,
        media_id: int,
        file_path: str,
        backend_used: str = "vlc",
    ) -> float:
        if not file_path:
            raise ValueError("file_path must not be empty")
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"media file not found: {file_path}")

        with self._lock:
            self._current_media_type = media_type
            self._current_media_id = media_id

        resume_pos = self._service.open(
            media_type,
            media_id,
            file_path,
            backend_used=backend_used,
        )

        self._event_bus.emit(
            PlaybackEventData(
                event=PlaybackEvent.MEDIA_OPENED,
                path=file_path,
            )
        )
        self._event_bus.emit(
            PlaybackEventData(
                event=PlaybackEvent.PLAYBACK_STARTED,
                path=file_path,
            )
        )

        return resume_pos

    def close(self) -> None:
        self._service.close()
        with self._lock:
            self._current_media_type = None
            self._current_media_id = None
        self._event_bus.emit(
            PlaybackEventData(event=PlaybackEvent.PLAYBACK_STOPPED)
        )

    def play(self) -> None:
        self._service.play()
        self._event_bus.emit(
            PlaybackEventData(event=PlaybackEvent.PLAYBACK_STARTED)
        )

    def pause(self) -> None:
        self._service.pause()
        self._event_bus.emit(
            PlaybackEventData(
                event=PlaybackEvent.PLAYBACK_PAUSED,
                position=self._service.get_position(),
            )
        )

    def toggle_pause(self) -> None:
        was_paused = self._service.is_paused()
        self._service.toggle_pause()
        if was_paused:
            self._event_bus.emit(
                PlaybackEventData(event=PlaybackEvent.PLAYBACK_STARTED)
            )
        else:
            self._event_bus.emit(
                PlaybackEventData(
                    event=PlaybackEvent.PLAYBACK_PAUSED,
                    position=self._service.get_position(),
                )
            )

    def stop(self) -> None:
        self._service.stop()
        with self._lock:
            self._current_media_type = None
            self._current_media_id = None
        self._event_bus.emit(
            PlaybackEventData(event=PlaybackEvent.PLAYBACK_STOPPED)
        )

    def seek(self, seconds: float) -> None:
        self._service.seek(seconds)
        self._event_bus.emit(
            PlaybackEventData(
                event=PlaybackEvent.POSITION_CHANGED,
                position=self._service.get_position(),
                duration=self._service.get_duration(),
            )
        )

    # -- state queries -------------------------------------------------------

    def get_position(self) -> float:
        return self._service.get_position()

    def get_duration(self) -> float:
        return self._service.get_duration()

    def is_open(self) -> bool:
        return self._service.is_open()

    def is_playing(self) -> bool:
        return self._service.is_playing()

    def is_paused(self) -> bool:
        return self._service.is_paused()

    # -- volume --------------------------------------------------------------

    def set_volume(self, volume: float) -> None:
        self._backend.set_volume(volume)

    def get_volume(self) -> float:
        return self._backend.get_volume()

    def mute(self) -> None:
        self._backend.mute()

    def unmute(self) -> None:
        self._backend.unmute()

    def is_muted(self) -> bool:
        return self._backend.is_muted()

    # -- playback rate -------------------------------------------------------

    def get_playback_rate(self) -> float:
        return self._backend.get_playback_rate()

    def set_playback_rate(self, rate: float) -> None:
        self._backend.set_playback_rate(rate)

    # -- audio tracks --------------------------------------------------------

    def get_audio_tracks(self) -> list[AudioTrack]:
        return self._backend.get_audio_tracks()

    def set_audio_track(self, track_id: int) -> None:
        self._backend.set_audio_track(track_id)

    def get_current_audio_track(self) -> int:
        return self._backend.get_current_audio_track()

    # -- subtitle tracks -----------------------------------------------------

    def get_subtitle_tracks(self) -> list[SubtitleTrack]:
        return self._backend.get_subtitle_tracks()

    def set_subtitle_track(self, track_id: int) -> None:
        self._backend.set_subtitle_track(track_id)

    def get_current_subtitle_track(self) -> int:
        return self._backend.get_current_subtitle_track()

    # -- video info ----------------------------------------------------------

    def get_video_tracks(self) -> list[VideoTrack]:
        return self._backend.get_video_tracks()

    def get_video_size(self) -> tuple[int, int] | None:
        return self._backend.get_video_size()

    def set_aspect_ratio(self, ratio: str | None) -> None:
        self._backend.set_aspect_ratio(ratio)

    def get_aspect_ratio(self) -> str | None:
        return self._backend.get_aspect_ratio()

    def set_crop_geometry(self, geometry: str | None) -> None:
        self._backend.set_crop_geometry(geometry)

    def get_crop_geometry(self) -> str | None:
        return self._backend.get_crop_geometry()

    def set_deinterlace(self, mode: str | None) -> None:
        self._backend.set_deinterlace(mode)

    # -- media info ----------------------------------------------------------

    def get_media_info(self) -> MediaInfo:
        return self._backend.get_media_info()

    # -- embedded video ------------------------------------------------------

    def set_video_window_id(self, win_id: int) -> None:
        self._backend.set_video_window_id(win_id)

    def set_video_widget(self, widget: Any) -> None:
        self._backend.set_video_widget(widget)

    # -- persistence ---------------------------------------------------------

    def save_position(self) -> None:
        self._service.save_position()

    def mark_completed(self) -> None:
        self._service.mark_completed()

    def is_completed(self, media_type: str, media_id: int) -> bool:
        return self._service.is_completed(media_type, media_id)

    def get_resume_position(
        self, media_type: str, media_id: int
    ) -> float:
        return self._service.get_resume_position(media_type, media_id)

    # -- cleanup -------------------------------------------------------------

    def release(self) -> None:
        with self._lock:
            self._current_media_type = None
            self._current_media_id = None
        self._service.close()
        self._backend.release()

    def __del__(self) -> None:  # pragma: no cover
        try:
            self.release()
        except Exception:
            pass

    # -- internal backend callback handlers -----------------------------------

    def _on_backend_end_reached(self) -> None:
        log.debug("Backend end reached — marking completed")
        with self._lock:
            mt = self._current_media_type
            mid = self._current_media_id

        if mt is not None and mid is not None:
            self._service.mark_completed()

        self._event_bus.emit(
            PlaybackEventData(
                event=PlaybackEvent.PLAYBACK_ENDED,
                position=self.get_position(),
                duration=self.get_duration(),
            )
        )

    def _on_backend_error(self, message: str) -> None:
        log.warning("Backend error: %s", message)
        self._event_bus.emit(
            PlaybackEventData(
                event=PlaybackEvent.PLAYBACK_ERROR,
                message=message,
            )
        )

    def _on_backend_state_changed(self, state: str) -> None:
        self._event_bus.emit(
            PlaybackEventData(
                event=PlaybackEvent.STATE_CHANGED,
                message=state,
                position=self.get_position(),
                duration=self.get_duration(),
            )
        )
