from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.media import MediaType

from .identifier import IdentificationResult
from .service import MetadataResolution, MetadataService

if TYPE_CHECKING:
    from app.services.music import MusicService

logger = logging.getLogger(__name__)


def _normalize_entity_type_for_provider(media_type) -> str:
    media_type_str = (
        media_type.value
        if hasattr(media_type, "value")
        else str(media_type)
    )
    if media_type_str in ("tv_show", "tv", "episode"):
        return "tv"
    return media_type_str


@dataclass(frozen=True)
class LibraryMetadataResult:
    resolution: MetadataResolution
    metadata_fetched: bool


class LibraryMetadataIntegration:
    """Bridge between library identification and metadata persistence."""

    def __init__(
        self,
        metadata_service: MetadataService,
        music_service: "MusicService | None" = None,
    ) -> None:
        self.metadata_service = metadata_service
        self.music_service = music_service

    def process_identification(
        self,
        result: IdentificationResult,
    ) -> LibraryMetadataResult:
        if result.media_type == MediaType.MUSIC:
            return self._process_music(result)

        resolution = self.metadata_service.resolve_identification(result)

        fetched = False

        if result.external_id:
            entity_type = _normalize_entity_type_for_provider(result.media_type)

            try:
                fetched = self.metadata_service.fetch_and_save_metadata(
                    entity_type=entity_type,
                    entity_id=resolution.entity_id,
                    external_id=result.external_id,
                    provider_name=result.provider,
                )
            except Exception:
                logger.warning(
                    "Metadata fetch failed for %s %r: continuing with local entity",
                    entity_type,
                    result.external_id,
                    exc_info=True,
                )

        return LibraryMetadataResult(
            resolution=resolution,
            metadata_fetched=fetched,
        )

    def _process_music(self, result: IdentificationResult) -> LibraryMetadataResult:
        if self.music_service is None:
            raise RuntimeError(
                "MusicService is required to process music identifications"
            )
        resolution = self.music_service.resolve_identification(result)
        return LibraryMetadataResult(
            resolution=MetadataResolution(
                entity_type="track",
                entity_id=resolution.track_id,
                created=resolution.created,
            ),
            metadata_fetched=False,
        )
