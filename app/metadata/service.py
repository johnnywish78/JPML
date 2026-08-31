from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .identifier import IdentificationResult
from .repository import MetadataRepository


@dataclass(frozen=True)
class MetadataResolution:
    entity_type: str
    entity_id: int
    created: bool


class MetadataService:
    """Application service coordinating identification and metadata persistence."""

    def __init__(self, repository: MetadataRepository) -> None:
        self.repository = repository

    def resolve_identification(
        self,
        result: IdentificationResult,
    ) -> MetadataResolution:
        entity_type = (
            result.media_type.value
            if hasattr(result.media_type, "value")
            else str(result.media_type)
        )

        existing = self.repository.find_by_external_id(
            entity_type=entity_type,
            provider=result.provider,
            external_id=result.external_id,
        )

        if existing is not None:
            return MetadataResolution(
                entity_type=entity_type,
                entity_id=existing,
                created=False,
            )

        entity_id = self._create_entity(result)

        self.repository.set_external_id(
            entity_type=entity_type,
            entity_id=entity_id,
            provider=result.provider,
            external_id=result.external_id,
            is_primary=True,
        )

        return MetadataResolution(
            entity_type=entity_type,
            entity_id=entity_id,
            created=True,
        )

    def save_metadata(
        self,
        *,
        entity_type: str,
        entity_id: int,
        provider: str,
        metadata: dict[str, Any],
        metadata_version: str | None = None,
        user_override: bool = False,
    ) -> None:
        title = metadata.get("title")
        year = metadata.get("year")
        overview = metadata.get("overview")

        self.repository.update_entity_metadata(
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            year=year,
            overview=overview,
        )

        self.repository.record_metadata_source(
            entity_type=entity_type,
            entity_id=entity_id,
            provider=provider,
            metadata_version=metadata_version,
            user_override=user_override,
        )

    def _create_entity(self, result: IdentificationResult) -> int:
        title = result.title
        year = result.year

        media_type = (
            result.media_type.value
            if hasattr(result.media_type, "value")
            else str(result.media_type)
        )

        if media_type == "movie":
            return self.repository.create_movie(title=title, year=year)

        if media_type == "tv":
            return self.repository.create_tv_show(title=title, year=year)

        raise ValueError(
            f"Unsupported identification media type: {result.media_type!r}"
        )
