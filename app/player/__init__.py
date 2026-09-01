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

    def get_state(self) -> PlayerState: ...

    def get_position(self) -> float: ...

    def get_duration(self) -> float: ...

    def is_open(self) -> bool: ...

    def is_playing(self) -> bool: ...

    def is_paused(self) -> bool: ...


class MockPlayerBackend:
    def __init__(self) -> None:
        self._state: PlayerState | None = None

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
