from __future__ import annotations

import enum
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)


class PlaybackEvent(enum.Enum):
    MEDIA_OPENED = "media_opened"
    PLAYBACK_STARTED = "playback_started"
    PLAYBACK_PAUSED = "playback_paused"
    PLAYBACK_STOPPED = "playback_stopped"
    PLAYBACK_ENDED = "playback_ended"
    PLAYBACK_ERROR = "playback_error"
    POSITION_CHANGED = "position_changed"
    DURATION_CHANGED = "duration_changed"
    STATE_CHANGED = "state_changed"


@dataclass(frozen=True)
class PlaybackEventData:
    event: PlaybackEvent
    position: float = 0.0
    duration: float = 0.0
    message: str = ""
    path: str = ""


PlaybackEventHandler = Callable[[PlaybackEventData], None]


class PlaybackEventBus:
    """Thread-safe pub/sub event bus for playback events.

    All dispatch happens synchronously on the calling thread.
    Consumers must not block or perform long-running work.
    """

    def __init__(self) -> None:
        self._handlers: dict[PlaybackEvent, list[PlaybackEventHandler]] = {}
        self._lock = threading.Lock()

    def subscribe(
        self,
        event: PlaybackEvent,
        handler: PlaybackEventHandler,
    ) -> None:
        with self._lock:
            self._handlers.setdefault(event, []).append(handler)

    def unsubscribe(
        self,
        event: PlaybackEvent,
        handler: PlaybackEventHandler,
    ) -> None:
        with self._lock:
            handlers = self._handlers.get(event, [])
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    def emit(self, data: PlaybackEventData) -> None:
        with self._lock:
            handlers = list(self._handlers.get(data.event, []))

        for handler in handlers:
            try:
                handler(data)
            except Exception:
                log.exception(
                    "error in playback event handler for %s", data.event.value
                )

    def clear(self) -> None:
        with self._lock:
            self._handlers.clear()
