from __future__ import annotations

from dataclasses import dataclass

from .identifier import IdentificationResult
from .service import MetadataResolution, MetadataService


@dataclass(frozen=True)
class LibraryMetadataResult:
    resolution: MetadataResolution
    metadata_fetched: bool


class LibraryMetadataIntegration:
    """Bridge between library identification and metadata persistence."""

    def __init__(self, metadata_service: MetadataService) -> None:
        self.metadata_service = metadata_service

    def process_identification(
        self,
        result: IdentificationResult,
    ) -> LibraryMetadataResult:
        resolution = self.metadata_service.resolve_identification(result)

        fetched = False

        if result.external_id:
            entity_type = (
                result.media_type.value
                if hasattr(result.media_type, "value")
                else str(result.media_type)
            )

            fetched = self.metadata_service.fetch_and_save_metadata(
                entity_type=entity_type,
                entity_id=resolution.entity_id,
                external_id=result.external_id,
            )

        return LibraryMetadataResult(
            resolution=resolution,
            metadata_fetched=fetched,
        )
