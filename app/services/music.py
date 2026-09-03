from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domain.media import Album, Artist, MusicTrack
from app.library.music_repository import MusicRepository
from app.metadata.identifier import IdentificationResult


@dataclass(frozen=True, slots=True)
class MusicResolution:
    artist_id: int
    album_id: int
    track_id: int
    created: bool


# handler(kind, name, artist_name) -> metadata dict (may contain "year")
MusicMetadataHandler = Callable[[str, str, str], dict[str, Any] | None]


class MusicService:
    """Application service for the music catalog.

    Resolution is fully local and deterministic: an IdentificationResult
    (produced by the filename identification engine) is mapped onto a
    get-or-create artist/album/track chain.

    External music metadata is pluggable through an optional
    MusicMetadataHandler. Without one, no external metadata is ever
    fabricated or requested.
    """

    def __init__(
        self,
        repository: MusicRepository,
        metadata_handler: MusicMetadataHandler | None = None,
    ) -> None:
        self._repo = repository
        self._metadata_handler = metadata_handler

    @property
    def repository(self) -> MusicRepository:
        return self._repo

    # -- resolution ----------------------------------------------------------

    def resolve_identification(
        self,
        result: IdentificationResult,
        *,
        duration_seconds: float | None = None,
    ) -> MusicResolution:
        artist_name = (result.artist or "").strip() or "Unknown Artist"
        album_name = (result.album or "").strip() or artist_name
        track_title = (result.title or "").strip() or "Unknown Track"

        artist_id, artist_created = self._repo.resolve_artist(artist_name)

        year: int | None = None
        if self._metadata_handler is not None:
            try:
                meta = self._metadata_handler("album", album_name, artist_name) or {}
                raw_year = meta.get("year")
                if raw_year is not None:
                    year = int(raw_year)
            except Exception:
                year = None

        album_id, album_created = self._repo.resolve_album(
            artist_id, album_name, year=year
        )

        track_id, track_created = self._repo.resolve_track(
            album_id,
            track_title,
            track_number=result.track_number,
            duration_seconds=duration_seconds,
            year=year,
        )
        return MusicResolution(
            artist_id=artist_id,
            album_id=album_id,
            track_id=track_id,
            created=artist_created or album_created or track_created,
        )

    # -- reads -----------------------------------------------------------------

    def get_track(self, track_id: int) -> MusicTrack | None:
        return self._repo.get_track(track_id)

    def get_album(self, album_id: int) -> Album | None:
        return self._repo.get_album(album_id)

    def get_artist(self, artist_id: int) -> Artist | None:
        return self._repo.get_artist(artist_id)

    # -- search (delegates to repository) --------------------------------------

    def search_artists(self, query: str, limit: int = 50) -> list[Artist]:
        return self._repo.search_artists(query, limit=limit)

    def search_albums(self, query: str, limit: int = 50) -> list[Album]:
        return self._repo.search_albums(query, limit=limit)

    def search_tracks(self, query: str, limit: int = 50) -> list[MusicTrack]:
        return self._repo.search_tracks(query, limit=limit)

    # -- file relationships ------------------------------------------------------

    def link_track_file(self, track_id: int, media_file_id: int) -> None:
        self._repo.link_track_file(track_id, media_file_id)

    def find_track_id_by_media_file(self, media_file_id: int) -> int | None:
        return self._repo.find_track_id_by_media_file(media_file_id)
