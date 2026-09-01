from __future__ import annotations

from app.library.playback_repository import PlaybackRepository
from app.player import PlayerBackend


class PlaybackService:
    """Coordinates PlayerBackend with persistent playback state."""

    def __init__(
        self,
        backend: PlayerBackend,
        repository: PlaybackRepository,
    ) -> None:
        self._backend = backend
        self._repo = repository
        self._media_type: str | None = None
        self._media_id: int | None = None

    @property
    def backend(self) -> PlayerBackend:
        return self._backend

    @property
    def repository(self) -> PlaybackRepository:
        return self._repo

    @property
    def media_file_id(self) -> int | None:
        # Backward-compatible property name.
        return self._media_id

    def get_resume_position(
        self,
        media_type: str,
        media_id: int,
    ) -> float:
        return self._repo.get_last_position(media_type, media_id)

    def open(
        self,
        media_type: str,
        media_id: int,
        file_path: str,
        backend_used: str | None = None,
    ) -> float:
        # Read the previous position BEFORE start_playback(), because
        # start_playback() intentionally resets an existing record.
        resume_pos = self._repo.get_last_position(media_type, media_id)

        self._backend.open(file_path)

        self._media_type = media_type
        self._media_id = media_id

        self._repo.start_playback(
            media_type,
            media_id,
            file_path,
            duration=self._backend.get_duration()
            if self._backend.is_open()
            else 0.0,
            backend_used=backend_used or "",
        )

        if resume_pos > 0:
            self._backend.seek(resume_pos)

        return resume_pos

    def close(self) -> None:
        self._persist_position()
        self._backend.close()
        self._reset_state()

    def play(self) -> None:
        self._backend.play()

    def pause(self) -> None:
        self._backend.pause()
        self._persist_position()

    def toggle_pause(self) -> None:
        was_paused = self._backend.is_paused()
        self._backend.toggle_pause()

        if not was_paused:
            self._persist_position()

    def stop(self) -> None:
        if (
            self._media_type is not None
            and self._media_id is not None
            and not self._repo.is_completed(
                self._media_type,
                self._media_id,
            )
        ):
            self._persist_position()

        self._backend.stop()
        self._reset_state()

    def seek(self, seconds: float) -> None:
        self._backend.seek(seconds)
        self._persist_position()

    def save_position(self) -> None:
        self._persist_position()

    def mark_completed(self) -> None:
        if self._media_type is not None and self._media_id is not None:
            self._repo.mark_completed(
                self._media_type,
                self._media_id,
            )

    def is_completed(
        self,
        media_type: str,
        media_id: int,
    ) -> bool:
        return self._repo.is_completed(media_type, media_id)

    def get_position(self) -> float:
        if self._backend.is_open():
            return self._backend.get_position()
        return 0.0

    def get_duration(self) -> float:
        if self._backend.is_open():
            return self._backend.get_duration()
        return 0.0

    def is_open(self) -> bool:
        return self._backend.is_open()

    def is_playing(self) -> bool:
        return self._backend.is_playing()

    def is_paused(self) -> bool:
        return self._backend.is_paused()

    def _persist_position(self) -> None:
        if (
            self._media_type is not None
            and self._media_id is not None
            and self._backend.is_open()
        ):
            self._repo.update_position(
                self._media_type,
                self._media_id,
                self._backend.get_position(),
            )

    def _reset_state(self) -> None:
        self._media_type = None
        self._media_id = None
