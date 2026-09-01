from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Callable

try:
    import vlc
except ImportError:
    vlc = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

BACKEND_NAME = "vlc"

# ---------------------------------------------------------------------------
# Value objects (no raw VLC objects leak outside this module)
# ---------------------------------------------------------------------------

VALID_PLAYBACK_RATES = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 4.0)


@dataclass(frozen=True)
class AudioTrack:
    id: int
    name: str
    language: str | None = None


@dataclass(frozen=True)
class SubtitleTrack:
    id: int
    name: str
    language: str | None = None


@dataclass(frozen=True)
class VideoTrack:
    id: int
    name: str
    codec: str | None = None
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class MediaInfo:
    path: str
    duration_ms: int = 0
    video_tracks: tuple[VideoTrack, ...] = ()
    audio_tracks: tuple[AudioTrack, ...] = ()
    subtitle_tracks: tuple[SubtitleTrack, ...] = ()
    video_width: int | None = None
    video_height: int | None = None
    codec: str | None = None


@dataclass
class PlaybackCallbacks:
    on_end_reached: Callable[[], None] | None = None
    on_error: Callable[[str], None] | None = None
    on_state_changed: Callable[[str], None] | None = None


# ---------------------------------------------------------------------------
# VLCPlayerBackend
# ---------------------------------------------------------------------------

class VLCPlayerBackend:
    """Production-quality libVLC playback backend.

    Thread-safety notes:
      - Public methods are safe to call from any thread.
      - libVLC callbacks arrive on internal threads; the backend marshals
        them into user-supplied callables that should be thread-safe
        themselves (e.g. Qt signal emissions).
    """

    def __init__(
        self,
        *,
        vlc_args: list[str] | None = None,
        callbacks: PlaybackCallbacks | None = None,
    ) -> None:
        if vlc is None:
            raise RuntimeError("python-vlc is not installed")

        args = vlc_args if vlc_args is not None else ["--quiet"]
        self._instance: vlc.Instance = vlc.Instance(*args)
        self._player: vlc.MediaPlayer = self._instance.media_player_new()
        self._current_media: vlc.Media | None = None
        self._path: str = ""
        self._callbacks = callbacks or PlaybackCallbacks()
        self._lock = threading.Lock()

        self._attach_events()

    # -- lifecycle -----------------------------------------------------------

    def open(self, path: str) -> None:
        if not path:
            raise ValueError("path must not be empty")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"media file not found: {path}")

        with self._lock:
            self._release_media()
            media = self._instance.media_new(path)
            self._current_media = media
            self._path = path
            self._player.set_media(media)
            self._attach_events()
            self._player.play()

    def close(self) -> None:
        with self._lock:
            self._detach_events()
            self._player.stop()
            self._release_media()
            self._path = ""

    def play(self) -> None:
        self._require_media()
        self._player.play()

    def pause(self) -> None:
        self._require_media()
        self._player.set_pause(1)

    def toggle_pause(self) -> None:
        self._require_media()
        self._player.pause()

    def stop(self) -> None:
        with self._lock:
            self._detach_events()
            self._player.stop()
            self._release_media()
            self._path = ""

    def seek(self, seconds: float) -> None:
        self._require_media()
        seconds = max(0.0, float(seconds))
        duration_s = self.get_duration()
        if duration_s > 0:
            seconds = min(seconds, duration_s)
        self._player.set_time(int(seconds * 1000))

    # -- volume --------------------------------------------------------------

    def set_volume(self, volume: float) -> None:
        self._require_media()
        clamped = max(0.0, min(1.0, float(volume)))
        self._player.audio_set_volume(int(clamped * 100))

    def get_volume(self) -> float:
        if not self._is_media_loaded():
            return 1.0
        return self._player.audio_get_volume() / 100.0

    def mute(self) -> None:
        self._require_media()
        self._player.audio_set_mute(True)

    def unmute(self) -> None:
        self._require_media()
        self._player.audio_set_mute(False)

    def is_muted(self) -> bool:
        if not self._is_media_loaded():
            return False
        return bool(self._player.audio_get_mute())

    # -- state queries -------------------------------------------------------

    def get_position(self) -> float:
        if not self._is_media_loaded():
            return 0.0
        t = self._player.get_time()
        if t < 0:
            return 0.0
        return t / 1000.0

    def get_duration(self) -> float:
        if not self._is_media_loaded():
            return 0.0
        d = self._player.get_length()
        if d <= 0:
            return 0.0
        return d / 1000.0

    def is_open(self) -> bool:
        return self._is_media_loaded()

    def is_playing(self) -> bool:
        if not self._is_media_loaded():
            return False
        state = self._player.get_state()
        return state == vlc.State.Playing

    def is_paused(self) -> bool:
        if not self._is_media_loaded():
            return False
        state = self._player.get_state()
        return state == vlc.State.Paused

    def get_state(self):  # noqa: ANN201 – returns PlayerState from __init__.py
        """Return a PlayerState snapshot compatible with the Protocol."""
        from app.player import PlayerState

        if not self._is_media_loaded():
            raise RuntimeError("No media loaded")
        return PlayerState(
            path=self._path,
            position_seconds=self.get_position(),
            duration_seconds=self.get_duration(),
            volume=self.get_volume(),
            is_paused=self.is_paused(),
        )

    # -- playback rate -------------------------------------------------------

    def get_playback_rate(self) -> float:
        if not self._is_media_loaded():
            return 1.0
        return self._player.get_rate()

    def set_playback_rate(self, rate: float) -> None:
        self._require_media()
        rate = float(rate)
        if rate <= 0:
            raise ValueError(f"playback rate must be positive, got {rate}")
        self._player.set_rate(rate)

    # -- audio tracks --------------------------------------------------------

    def get_audio_tracks(self) -> list[AudioTrack]:
        if not self._is_media_loaded():
            return []
        tracks: list[AudioTrack] = []
        for tid, raw_name in self._player.audio_get_track_description():
            if tid < 0:
                continue
            name = raw_name.decode("utf-8", errors="replace") if isinstance(raw_name, bytes) else str(raw_name)
            tracks.append(AudioTrack(id=tid, name=name))
        return tracks

    def set_audio_track(self, track_id: int) -> None:
        self._require_media()
        self._player.audio_set_track(track_id)

    def get_current_audio_track(self) -> int:
        if not self._is_media_loaded():
            return -1
        return self._player.audio_get_track()

    # -- subtitle tracks -----------------------------------------------------

    def get_subtitle_tracks(self) -> list[SubtitleTrack]:
        if not self._is_media_loaded():
            return []
        tracks: list[SubtitleTrack] = []
        for tid, raw_name in self._player.video_get_spu_description():
            if tid < 0:
                continue
            name = raw_name.decode("utf-8", errors="replace") if isinstance(raw_name, bytes) else str(raw_name)
            tracks.append(SubtitleTrack(id=tid, name=name))
        return tracks

    def set_subtitle_track(self, track_id: int) -> None:
        self._require_media()
        self._player.video_set_spu(track_id)

    def get_current_subtitle_track(self) -> int:
        if not self._is_media_loaded():
            return -1
        return self._player.video_get_spu()

    # -- video info ----------------------------------------------------------

    def get_video_tracks(self) -> list[VideoTrack]:
        if not self._is_media_loaded():
            return []
        tracks: list[VideoTrack] = []
        for tid, raw_name in self._player.video_get_track_description():
            if tid < 0:
                continue
            name = raw_name.decode("utf-8", errors="replace") if isinstance(raw_name, bytes) else str(raw_name)
            tracks.append(VideoTrack(id=tid, name=name))
        return tracks

    def get_video_size(self) -> tuple[int, int] | None:
        if not self._is_media_loaded():
            return None
        size = self._player.video_get_size(0)
        if size and size[0] > 0 and size[1] > 0:
            return (size[0], size[1])
        return None

    def set_aspect_ratio(self, ratio: str | None) -> None:
        self._require_media()
        self._player.video_set_aspect_ratio(ratio)

    def get_aspect_ratio(self) -> str | None:
        if not self._is_media_loaded():
            return None
        return self._player.video_get_aspect_ratio()

    def set_crop_geometry(self, geometry: str | None) -> None:
        self._require_media()
        self._player.video_set_crop_geometry(geometry)

    def get_crop_geometry(self) -> str | None:
        if not self._is_media_loaded():
            return None
        return self._player.video_get_crop_geometry()

    def set_deinterlace(self, mode: str | None) -> None:
        self._require_media()
        self._player.video_set_deinterlace(mode)

    # -- media info ----------------------------------------------------------

    def get_media_info(self) -> MediaInfo:
        if not self._is_media_loaded():
            return MediaInfo(path="")
        return MediaInfo(
            path=self._path,
            duration_ms=self._player.get_length(),
            video_tracks=tuple(self.get_video_tracks()),
            audio_tracks=tuple(self.get_audio_tracks()),
            subtitle_tracks=tuple(self.get_subtitle_tracks()),
            video_width=self._video_dim(0),
            video_height=self._video_dim(1),
            codec=None,
        )

    # -- embedded video ------------------------------------------------------

    def set_video_window_id(self, win_id: int) -> None:
        """Attach video output to an existing native window handle.

        On X11 this calls ``set_xwindow()``; on other platforms the
        appropriate libVLC method is used.
        """
        self._require_media()
        self._player.set_xwindow(win_id)

    def set_video_widget(self, widget: object) -> None:
        """Convenience wrapper for PyQt/PySide widgets.

        Extracts the native window id from *widget* (must have a
        ``winId()`` method, as Qt widgets do) and delegates to
        :meth:`set_video_window_id`.
        """
        wid = int(widget.winId())
        self.set_video_window_id(wid)

    # -- callbacks -----------------------------------------------------------

    def set_callbacks(self, callbacks: PlaybackCallbacks) -> None:
        self._callbacks = callbacks

    # -- resource management -------------------------------------------------

    def release(self) -> None:
        """Release all libVLC resources.  The backend is unusable after this."""
        with self._lock:
            self._detach_events()
            self._player.stop()
            self._release_media()
            self._player.release()
            self._player = None  # type: ignore[assignment]
            self._instance.release()
            self._instance = None  # type: ignore[assignment]

    def __del__(self) -> None:  # pragma: no cover – safety net
        try:
            self.release()
        except Exception:
            pass

    # -- internals -----------------------------------------------------------

    def _is_media_loaded(self) -> bool:
        return self._current_media is not None and self._path != ""

    def _require_media(self) -> None:
        if not self._is_media_loaded():
            raise RuntimeError("No media loaded")

    def _release_media(self) -> None:
        if self._current_media is not None:
            try:
                self._current_media.release()
            except Exception:
                pass
            self._current_media = None

    def _video_dim(self, index: int) -> int | None:
        if not self._is_media_loaded():
            return None
        try:
            size = self._player.video_get_size(0)
            if size and index < len(size) and size[index] > 0:
                return size[index]
        except Exception:
            pass
        return None

    # -- event handling ------------------------------------------------------

    _EVENT_MAP: dict[int, str] = {}

    _events_attached: bool = False

    def _attach_events(self) -> None:
        if self._events_attached:
            return
        em = self._player.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)
        em.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_error)
        em.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_playing)
        em.event_attach(vlc.EventType.MediaPlayerPaused, self._on_paused)
        em.event_attach(vlc.EventType.MediaPlayerStopped, self._on_stopped)
        self._events_attached = True

    def _detach_events(self) -> None:
        if not self._events_attached:
            return
        if self._player is None:
            return
        em = self._player.event_manager()
        em.event_detach(vlc.EventType.MediaPlayerEndReached)
        em.event_detach(vlc.EventType.MediaPlayerEncounteredError)
        em.event_detach(vlc.EventType.MediaPlayerPlaying)
        em.event_detach(vlc.EventType.MediaPlayerPaused)
        em.event_detach(vlc.EventType.MediaPlayerStopped)
        self._events_attached = False

    def _on_end_reached(self, event: object) -> None:  # noqa: ARG002
        log.debug("VLC end reached")
        cb = self._callbacks.on_end_reached
        if cb is not None:
            try:
                cb()
            except Exception:
                log.exception("error in on_end_reached callback")

    def _on_error(self, event: object) -> None:  # noqa: ARG002
        log.warning("VLC encountered an error")
        cb = self._callbacks.on_error
        if cb is not None:
            try:
                cb("VLC playback error")
            except Exception:
                log.exception("error in on_error callback")

    def _on_playing(self, event: object) -> None:  # noqa: ARG002
        cb = self._callbacks.on_state_changed
        if cb is not None:
            try:
                cb("playing")
            except Exception:
                pass

    def _on_paused(self, event: object) -> None:  # noqa: ARG002
        cb = self._callbacks.on_state_changed
        if cb is not None:
            try:
                cb("paused")
            except Exception:
                pass

    def _on_stopped(self, event: object) -> None:  # noqa: ARG002
        cb = self._callbacks.on_state_changed
        if cb is not None:
            try:
                cb("stopped")
            except Exception:
                pass
