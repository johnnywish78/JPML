from __future__ import annotations

import logging
import os
import threading
from typing import Any

try:
    import mpv
except ImportError:
    mpv = None  # type: ignore[assignment]

from app.player import (
    AudioTrack,
    MediaInfo,
    PlaybackCallbacks,
    PlayerState,
    SubtitleTrack,
    VideoTrack,
)

log = logging.getLogger(__name__)

BACKEND_NAME = "mpv"


class MPVPlayerBackend:
    """Production-quality libmpv playback backend via python-mpv.

    Thread-safety notes:
      - Public methods are safe to call from any thread.
      - MPV events arrive on an internal thread; the backend marshals
        them into user-supplied callables that should be thread-safe
        themselves (e.g. Qt signal emissions).

    Embedding:
      Use set_video_window_id() or set_video_widget() to embed video
      output into an existing native window handle.  On Wayland,
      embedding may require XWayland; pass a valid X11 window id.

    Property access:
      python-mpv uses attribute-based property access (e.g.
      ``self._player.volume``).  The ``get_property`` / ``set_property``
      methods are not part of the public API.
    """

    def __init__(
        self,
        *,
        mpv_args: list[str] | None = None,
        callbacks: PlaybackCallbacks | None = None,
    ) -> None:
        if mpv is None:
            raise RuntimeError("python-mpv is not installed")

        args = list(mpv_args) if mpv_args is not None else []

        self._player: mpv.MPV | None = mpv.MPV(
            *args,
            pause=True,
            log_handler=lambda level, prefix, msg: log.log(
                {"debug": logging.DEBUG, "v": logging.DEBUG,
                 "info": logging.INFO, "warn": logging.WARNING,
                 "error": logging.ERROR, "fatal": logging.FATAL,
                 }.get(str(level), logging.DEBUG),
                "[%s] %s", prefix, msg,
            ),
            loglevel="debug" if logging.getLogger().level <= logging.DEBUG else "v",
        )

        self._path: str = ""
        self._callbacks = callbacks or PlaybackCallbacks()
        self._lock = threading.Lock()
        self._media_loaded = False

        self._attach_events()

    # -- lifecycle -----------------------------------------------------------

    def open(self, path: str) -> None:
        if not path:
            raise ValueError("path must not be empty")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"media file not found: {path}")
        if self._player is None:
            raise RuntimeError("Backend has been released")

        with self._lock:
            self._player.command("loadfile", path, "replace")
            self._path = path
            self._media_loaded = True

    def close(self) -> None:
        if self._player is None:
            return
        with self._lock:
            try:
                self._player.command("stop")
            except Exception:
                pass
            self._path = ""
            self._media_loaded = False

    def play(self) -> None:
        self._require_media()
        self._player.pause = False  # type: ignore[union-attr]

    def pause(self) -> None:
        self._require_media()
        self._player.pause = True  # type: ignore[union-attr]

    def toggle_pause(self) -> None:
        self._require_media()
        self._player.pause = not self._player.pause  # type: ignore[union-attr]

    def stop(self) -> None:
        if self._player is None:
            return
        with self._lock:
            try:
                self._player.command("stop")
            except Exception:
                pass
            self._path = ""
            self._media_loaded = False

    def seek(self, seconds: float) -> None:
        self._require_media()
        seconds = max(0.0, float(seconds))
        duration_s = self.get_duration()
        if duration_s > 0:
            seconds = min(seconds, duration_s)
        try:
            self._player.command("seek", seconds, "absolute")
        except Exception:
            pass

    # -- volume --------------------------------------------------------------

    def set_volume(self, volume: float) -> None:
        self._require_media()
        clamped = max(0.0, min(1.0, float(volume)))
        self._player.volume = clamped * 100.0  # type: ignore[union-attr]

    def get_volume(self) -> float:
        if not self._is_media_loaded():
            return 1.0
        try:
            return self._player.volume / 100.0  # type: ignore[union-attr]
        except Exception:
            return 1.0

    def mute(self) -> None:
        self._require_media()
        self._player.mute = True  # type: ignore[union-attr]

    def unmute(self) -> None:
        self._require_media()
        self._player.mute = False  # type: ignore[union-attr]

    def is_muted(self) -> bool:
        if not self._is_media_loaded():
            return False
        try:
            return bool(self._player.mute)  # type: ignore[union-attr]
        except Exception:
            return False

    # -- state queries -------------------------------------------------------

    def get_position(self) -> float:
        if not self._is_media_loaded():
            return 0.0
        try:
            pos = self._player.time_pos  # type: ignore[union-attr]
            return pos if pos is not None else 0.0
        except Exception:
            return 0.0

    def get_duration(self) -> float:
        if not self._is_media_loaded():
            return 0.0
        try:
            dur = self._player.duration  # type: ignore[union-attr]
            return dur if dur is not None else 0.0
        except Exception:
            return 0.0

    def is_open(self) -> bool:
        return self._is_media_loaded()

    def is_playing(self) -> bool:
        if not self._is_media_loaded():
            return False
        try:
            pause = self._player.pause  # type: ignore[union-attr]
            core_idle = self._player.core_idle  # type: ignore[union-attr]
            return not pause and not core_idle
        except Exception:
            return False

    def is_paused(self) -> bool:
        if not self._is_media_loaded():
            return False
        try:
            return bool(self._player.pause)  # type: ignore[union-attr]
        except Exception:
            return False

    def get_state(self) -> PlayerState:  # noqa: ANN201
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
        try:
            return self._player.speed  # type: ignore[union-attr]
        except Exception:
            return 1.0

    def set_playback_rate(self, rate: float) -> None:
        self._require_media()
        rate = float(rate)
        if rate <= 0:
            raise ValueError(f"playback rate must be positive, got {rate}")
        self._player.speed = rate  # type: ignore[union-attr]

    # -- audio tracks --------------------------------------------------------

    def get_audio_tracks(self) -> list[AudioTrack]:
        if not self._is_media_loaded():
            return []
        try:
            track_list = self._player.track_list  # type: ignore[union-attr]
        except Exception:
            return []
        tracks: list[AudioTrack] = []
        for t in track_list:
            if t.get("type") == "audio":
                tracks.append(AudioTrack(
                    id=t.get("id", 0),
                    name=t.get("title", t.get("decoder-desc", f"Audio {t.get('id', 0)}")),
                    language=t.get("lang"),
                ))
        return tracks

    def set_audio_track(self, track_id: int) -> None:
        self._require_media()
        self._player.aid = track_id  # type: ignore[union-attr]

    def get_current_audio_track(self) -> int:
        if not self._is_media_loaded():
            return -1
        try:
            return self._player.aid  # type: ignore[union-attr]
        except Exception:
            return -1

    # -- subtitle tracks -----------------------------------------------------

    def get_subtitle_tracks(self) -> list[SubtitleTrack]:
        if not self._is_media_loaded():
            return []
        try:
            track_list = self._player.track_list  # type: ignore[union-attr]
        except Exception:
            return []
        tracks: list[SubtitleTrack] = []
        for t in track_list:
            if t.get("type") == "sub":
                tracks.append(SubtitleTrack(
                    id=t.get("id", 0),
                    name=t.get("title", t.get("decoder-desc", f"Sub {t.get('id', 0)}")),
                    language=t.get("lang"),
                ))
        return tracks

    def set_subtitle_track(self, track_id: int) -> None:
        self._require_media()
        self._player.sid = track_id  # type: ignore[union-attr]

    def get_current_subtitle_track(self) -> int:
        if not self._is_media_loaded():
            return -1
        try:
            return self._player.sid  # type: ignore[union-attr]
        except Exception:
            return -1

    # -- video info ----------------------------------------------------------

    def get_video_tracks(self) -> list[VideoTrack]:
        if not self._is_media_loaded():
            return []
        try:
            track_list = self._player.track_list  # type: ignore[union-attr]
        except Exception:
            return []
        tracks: list[VideoTrack] = []
        for t in track_list:
            if t.get("type") == "video":
                tracks.append(VideoTrack(
                    id=t.get("id", 0),
                    name=t.get("title", t.get("decoder-desc", f"Video {t.get('id', 0)}")),
                    codec=t.get("codec"),
                    width=t.get("demux-w"),
                    height=t.get("demux-h"),
                ))
        return tracks

    def get_video_size(self) -> tuple[int, int] | None:
        if not self._is_media_loaded():
            return None
        try:
            w = self._player.width  # type: ignore[union-attr]
            h = self._player.height  # type: ignore[union-attr]
            if w and h and w > 0 and h > 0:
                return (int(w), int(h))
        except Exception:
            pass
        return None

    def set_aspect_ratio(self, ratio: str | None) -> None:
        self._require_media()
        if ratio is None:
            self._player.video_aspect_override = "no"  # type: ignore[union-attr]
        else:
            self._player.video_aspect_override = ratio  # type: ignore[union-attr]

    def get_aspect_ratio(self) -> str | None:
        if not self._is_media_loaded():
            return None
        try:
            val = self._player.video_aspect_override  # type: ignore[union-attr]
            if val in (None, "no", ""):
                return None
            return str(val)
        except Exception:
            return None

    def set_crop_geometry(self, geometry: str | None) -> None:
        self._require_media()
        if geometry is None:
            self._player.video_crop_geometry = "no"  # type: ignore[union-attr]
        else:
            self._player.video_crop_geometry = geometry  # type: ignore[union-attr]

    def get_crop_geometry(self) -> str | None:
        if not self._is_media_loaded():
            return None
        try:
            val = self._player.video_crop_geometry  # type: ignore[union-attr]
            if val in (None, "no", ""):
                return None
            return str(val)
        except Exception:
            return None

    def set_deinterlace(self, mode: str | None) -> None:
        self._require_media()
        if mode is None or mode.lower() in ("off", "no", "false", ""):
            self._player.deinterlace = False  # type: ignore[union-attr]
        else:
            self._player.deinterlace = True  # type: ignore[union-attr]

    # -- media info ----------------------------------------------------------

    def get_media_info(self) -> MediaInfo:
        if not self._is_media_loaded():
            return MediaInfo(path="")
        dur_ms = 0
        try:
            dur_s = self._player.duration  # type: ignore[union-attr]
            if dur_s:
                dur_ms = int(dur_s * 1000)
        except Exception:
            pass
        return MediaInfo(
            path=self._path,
            duration_ms=dur_ms,
            video_tracks=tuple(self.get_video_tracks()),
            audio_tracks=tuple(self.get_audio_tracks()),
            subtitle_tracks=tuple(self.get_subtitle_tracks()),
            video_width=self._video_dim("width"),
            video_height=self._video_dim("height"),
            codec=None,
        )

    # -- embedded video ------------------------------------------------------

    def set_video_window_id(self, win_id: int) -> None:
        """Attach video output to an existing native window handle.

        On X11/XWayland this sets the mpv 'wid' property.
        On pure Wayland, embedding requires XWayland; the window id
        must be a valid X11 window.
        """
        self._require_media()
        self._player.wid = win_id  # type: ignore[union-attr]

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
        """Release all mpv resources.  The backend is unusable after this."""
        if self._player is None:
            return
        with self._lock:
            try:
                self._player.command("stop")
            except Exception:
                pass
            try:
                self._player.terminate()
            except Exception:
                pass
            self._player = None
            self._path = ""
            self._media_loaded = False

    def __del__(self) -> None:  # pragma: no cover – safety net
        try:
            self.release()
        except Exception:
            pass

    # -- internals -----------------------------------------------------------

    def _is_media_loaded(self) -> bool:
        return self._media_loaded and self._player is not None and self._path != ""

    def _require_media(self) -> None:
        if not self._is_media_loaded():
            raise RuntimeError("No media loaded")

    def _video_dim(self, prop: str) -> int | None:
        if not self._is_media_loaded():
            return None
        try:
            val = getattr(self._player, prop)
            if val and int(val) > 0:
                return int(val)
        except Exception:
            pass
        return None

    # -- event handling ------------------------------------------------------

    def _attach_events(self) -> None:
        if self._player is None:
            return
        try:
            self._player.observe_property("eof-reached", self._on_eof)
            self._player.observe_property("pause", self._on_pause_changed)
            self._player.observe_property("core-idle", self._on_core_idle)
        except Exception:
            log.debug("Failed to attach mpv observers", exc_info=True)

    def _on_eof(self, name: str, value: Any) -> None:  # noqa: ARG002
        if value is True:
            log.debug("MPV end reached")
            cb = self._callbacks.on_end_reached
            if cb is not None:
                try:
                    cb()
                except Exception:
                    log.exception("error in on_end_reached callback")

    def _on_pause_changed(self, name: str, value: Any) -> None:  # noqa: ARG002
        cb = self._callbacks.on_state_changed
        if cb is not None:
            try:
                cb("paused" if value else "playing")
            except Exception:
                pass

    def _on_core_idle(self, name: str, value: Any) -> None:  # noqa: ARG002
        cb = self._callbacks.on_state_changed
        if cb is not None:
            try:
                if value is True:
                    cb("stopped")
            except Exception:
                pass
