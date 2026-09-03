from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


# ---------------------------------------------------------------------------
# Shared value objects (used by all backend implementations)
# ---------------------------------------------------------------------------


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
# Player state and protocol
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PlayerState:
    path: str
    position_seconds: float = 0.0
    duration_seconds: float = 0.0
    volume: float = 1.0
    is_paused: bool = True


class PlayerBackend(Protocol):
    def open(self, path: str) -> None: ...

    def close(self) -> None: ...

    def play(self) -> None: ...

    def pause(self) -> None: ...

    def toggle_pause(self) -> None: ...

    def stop(self) -> None: ...

    def seek(self, seconds: float) -> None: ...

    def set_volume(self, volume: float) -> None: ...

    def get_volume(self) -> float: ...

    def mute(self) -> None: ...

    def unmute(self) -> None: ...

    def is_muted(self) -> bool: ...

    def get_state(self) -> PlayerState: ...

    def get_position(self) -> float: ...

    def get_duration(self) -> float: ...

    def is_open(self) -> bool: ...

    def is_playing(self) -> bool: ...

    def is_paused(self) -> bool: ...

    def get_playback_rate(self) -> float: ...

    def set_playback_rate(self, rate: float) -> None: ...

    def get_audio_tracks(self) -> list[AudioTrack]: ...

    def set_audio_track(self, track_id: int) -> None: ...

    def get_current_audio_track(self) -> int: ...

    def get_subtitle_tracks(self) -> list[SubtitleTrack]: ...

    def set_subtitle_track(self, track_id: int) -> None: ...

    def get_current_subtitle_track(self) -> int: ...

    def get_video_tracks(self) -> list[VideoTrack]: ...

    def get_video_size(self) -> tuple[int, int] | None: ...

    def set_aspect_ratio(self, ratio: str | None) -> None: ...

    def get_aspect_ratio(self) -> str | None: ...

    def set_crop_geometry(self, geometry: str | None) -> None: ...

    def get_crop_geometry(self) -> str | None: ...

    def set_deinterlace(self, mode: str | None) -> None: ...

    def get_media_info(self) -> MediaInfo: ...

    def set_video_window_id(self, win_id: int) -> None: ...

    def set_video_widget(self, widget: object) -> None: ...

    def set_callbacks(self, callbacks: PlaybackCallbacks) -> None: ...

    def release(self) -> None: ...


class MockPlayerBackend:
    def __init__(self) -> None:
        self._state: PlayerState | None = None
        self._callbacks = PlaybackCallbacks()
        self._muted = False
        self._playback_rate = 1.0
        self._audio_tracks: list[AudioTrack] = []
        self._subtitle_tracks: list[SubtitleTrack] = []
        self._video_tracks: list[VideoTrack] = []
        self._current_audio_track = -1
        self._current_subtitle_track = -1
        self._aspect_ratio: str | None = None
        self._crop_geometry: str | None = None
        self._deinterlace_mode: str | None = None
        self._released = False

    def open(self, path: str) -> None:
        self._state = PlayerState(path=path)

    def close(self) -> None:
        self._state = None

    def play(self) -> None:
        if self._state is None:
            raise RuntimeError("No media loaded")
        self._state.is_paused = False

    def pause(self) -> None:
        if self._state is None:
            raise RuntimeError("No media loaded")
        self._state.is_paused = True

    def toggle_pause(self) -> None:
        if self._state is None:
            raise RuntimeError("No media loaded")
        self._state.is_paused = not self._state.is_paused

    def stop(self) -> None:
        self._state = None

    def seek(self, seconds: float) -> None:
        if self._state is None:
            raise RuntimeError("No media loaded")
        self._state.position_seconds = max(0.0, seconds)

    def set_volume(self, volume: float) -> None:
        if self._state is None:
            raise RuntimeError("No media loaded")
        self._state.volume = max(0.0, min(1.0, volume))

    def get_volume(self) -> float:
        if self._state is None:
            return 1.0
        return self._state.volume

    def mute(self) -> None:
        if self._state is None:
            raise RuntimeError("No media loaded")
        self._muted = True

    def unmute(self) -> None:
        if self._state is None:
            raise RuntimeError("No media loaded")
        self._muted = False

    def is_muted(self) -> bool:
        return self._muted

    def get_state(self) -> PlayerState:
        if self._state is None:
            raise RuntimeError("No media loaded")
        return self._state

    def get_position(self) -> float:
        if self._state is None:
            raise RuntimeError("No media loaded")
        return self._state.position_seconds

    def get_duration(self) -> float:
        if self._state is None:
            raise RuntimeError("No media loaded")
        return self._state.duration_seconds

    def is_open(self) -> bool:
        return self._state is not None

    def is_playing(self) -> bool:
        return self._state is not None and not self._state.is_paused

    def is_paused(self) -> bool:
        return self._state is not None and self._state.is_paused

    def get_playback_rate(self) -> float:
        return self._playback_rate

    def set_playback_rate(self, rate: float) -> None:
        self._playback_rate = float(rate)

    def get_audio_tracks(self) -> list[AudioTrack]:
        return list(self._audio_tracks)

    def set_audio_track(self, track_id: int) -> None:
        self._current_audio_track = track_id

    def get_current_audio_track(self) -> int:
        return self._current_audio_track

    def get_subtitle_tracks(self) -> list[SubtitleTrack]:
        return list(self._subtitle_tracks)

    def set_subtitle_track(self, track_id: int) -> None:
        self._current_subtitle_track = track_id

    def get_current_subtitle_track(self) -> int:
        return self._current_subtitle_track

    def get_video_tracks(self) -> list[VideoTrack]:
        return list(self._video_tracks)

    def get_video_size(self) -> tuple[int, int] | None:
        return None

    def set_aspect_ratio(self, ratio: str | None) -> None:
        self._aspect_ratio = ratio

    def get_aspect_ratio(self) -> str | None:
        return self._aspect_ratio

    def set_crop_geometry(self, geometry: str | None) -> None:
        self._crop_geometry = geometry

    def get_crop_geometry(self) -> str | None:
        return self._crop_geometry

    def set_deinterlace(self, mode: str | None) -> None:
        self._deinterlace_mode = mode

    def get_media_info(self) -> MediaInfo:
        if self._state is None:
            return MediaInfo(path="")
        return MediaInfo(path=self._state.path)

    def set_video_window_id(self, win_id: int) -> None:
        pass

    def set_video_widget(self, widget: object) -> None:
        pass

    def set_callbacks(self, callbacks: PlaybackCallbacks) -> None:
        self._callbacks = callbacks

    def release(self) -> None:
        self._state = None
        self._released = True
