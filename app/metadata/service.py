from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from .identifier import IdentificationResult
from .registry import MetadataProviderRegistry
from .repository import MetadataRepository
from .provider import MetadataProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetadataResolution:
    entity_type: str
    entity_id: int
    created: bool


class MetadataService:
    """Application service coordinating identification and metadata persistence."""

    def __init__(
        self,
        repository: MetadataRepository,
        provider: MetadataProvider | None = None,
        registry: MetadataProviderRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.registry = registry

    def _resolve_provider(
        self,
        provider_name: str | None,
        fallback: MetadataProvider | None = None,
    ) -> MetadataProvider | None:
        if provider_name and self.registry and self.registry.has(provider_name):
            return self.registry.get(provider_name)
        return fallback or self.provider

    def _select_provider(
        self,
        provider: MetadataProvider | None,
        provider_name: str | None,
    ) -> MetadataProvider | None:
        if provider is not None:
            return provider
        if provider_name and self.registry and self.registry.has(provider_name):
            return self.registry.get(provider_name)
        return self.provider

    def resolve_identification(
        self,
        result: IdentificationResult,
    ) -> MetadataResolution:
        entity_type = self._normalize_entity_type(result)

        if result.provider and result.external_id:
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

        if result.provider and result.external_id:
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

    @staticmethod
    def _normalize_entity_type(result: IdentificationResult) -> str:
        media_type = (
            result.media_type.value
            if hasattr(result.media_type, "value")
            else str(result.media_type)
        )
        if media_type in ("tv_show", "tv", "episode"):
            return "tv"
        return media_type

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

        genres = metadata.get("genres") or []

        if entity_type == "movie":
            self.repository.set_movie_genres(
                movie_id=entity_id,
                genres=list(genres),
            )
        elif entity_type == "tv":
            self.repository.set_tv_genres(
                tv_show_id=entity_id,
                genres=list(genres),
            )

        self.repository.record_metadata_source(
            entity_type=entity_type,
            entity_id=entity_id,
            provider=provider,
            metadata_version=metadata_version,
            user_override=user_override,
        )


    def fetch_and_save_metadata(
        self,
        *,
        entity_type: str,
        entity_id: int,
        external_id: str,
        provider: MetadataProvider | None = None,
        provider_name: str | None = None,
        user_override: bool = False,
    ) -> bool:
        """Fetch provider metadata and persist it.

        Returns True when metadata was fetched and saved, False when
        the provider has no record for the requested external ID.
        """
        active_provider = self._select_provider(provider, provider_name)
        if active_provider is None:
            raise ValueError("metadata provider is required")

        metadata = active_provider.fetch_metadata(
            entity_type=entity_type,
            external_id=external_id,
        )

        if metadata is None:
            return False

        self.save_metadata(
            entity_type=entity_type,
            entity_id=entity_id,
            provider=active_provider.name,
            metadata={
                "title": metadata.title,
                "year": metadata.year,
                "overview": metadata.overview,
                "genres": list(metadata.genres),
                "external_id": metadata.external_id,
                "metadata_version": metadata.metadata_version,
            },
            metadata_version=metadata.metadata_version,
            user_override=user_override,
        )

        return True

    def _create_entity(self, result: IdentificationResult) -> int:
        title = result.title
        year = result.year

        media_type = self._normalize_entity_type(result)

        if media_type == "movie":
            return self.repository.create_movie(title=title, year=year)

        if media_type == "tv":
            return self.repository.create_tv_show(title=title, year=year)

        raise ValueError(
            f"Unsupported identification media type: {result.media_type!r}"
        )
